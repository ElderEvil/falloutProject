"""Incident round engine: defender-less outcomes, damage, victory, and XP."""

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.dweller import dweller as crud_dweller
from app.models.dweller import Dweller
from app.models.incident import Incident, IncidentStatus, IncidentType, get_incident_definition
from app.schemas.incident import IncidentRoundResult
from app.services.combat import incident_math, incident_publishing
from app.services.combat.incident_spawning import spread_incident
from app.services.notification_service import notification_service
from app.services.radiation_service import apply_radiation_gain

logger = logging.getLogger(__name__)


async def no_defender_outcome(db_session: AsyncSession, incident: Incident) -> IncidentRoundResult:
    """An active incident nobody responds to: spread it, keep waiting, or lose it."""
    if (
        incident.elapsed_time() >= incident.duration
        and incident.spread_count < game_config.incident.max_spread_count
        and await spread_incident(db_session, incident)
    ):
        await db_session.commit()
        await incident_publishing.publish_sse(incident, "incident_spreading")
        return IncidentRoundResult(no_defenders=True)

    if incident.spread_count >= game_config.incident.max_spread_count or incident.elapsed_time() >= incident.duration:
        incident.resolve(success=False)
        incident_publishing.record_event(
            db_session,
            incident,
            "failed",
            f"Failed to {get_incident_definition(incident.type).objective.value} before escalation.",
        )
        db_session.add(incident)
        await db_session.commit()
        await incident_publishing.publish_sse(incident, "incident_resolved", success=False)
        await incident_publishing.notify_resolution(db_session, incident, success=False)
    return IncidentRoundResult(no_defenders=True)


async def apply_damage(
    db_session: AsyncSession, incident: Incident, dwellers: list[Dweller], damage_to_dwellers: float
) -> tuple[int, int]:
    """Distribute incoming damage across responders; deaths stay pending for the round commit."""
    from app.core.enums import DeathCauseEnum
    from app.services.family.death_service import death_service

    damaged_count = 0
    deaths_count = 0
    total_damage = max(0, int(damage_to_dwellers))
    damage_per_dweller, remainder = divmod(total_damage, len(dwellers))
    for index, dweller in enumerate(dwellers):
        dweller_damage = damage_per_dweller + (1 if index < remainder else 0)
        new_health = max(0, dweller.health - dweller_damage)

        if (
            incident.type == IncidentType.RADSCORPION_ATTACK and dweller_damage > 1
        ):  # TODO: should depend on enemy type, not incident type, need to think through
            radiation_damage = min(dweller_damage - 1, dweller_damage // 2)
            apply_radiation_gain(dweller, radiation_damage)
            db_session.add(dweller)

        new_health = min(new_health, dweller.effective_max_health)

        if new_health != dweller.health:
            # Direct update - SQLAlchemy session tracks the object, no need to refresh
            dweller.health = new_health
            db_session.add(dweller)
            damaged_count += 1

            # Check for death from incident
            if new_health <= 0 and not dweller.is_dead:
                await death_service.mark_as_dead(db_session, dweller, DeathCauseEnum.INCIDENT, commit=False)
                deaths_count += 1
                logger.info(f"Dweller {dweller.first_name} {dweller.last_name} died during incident")

    return damaged_count, deaths_count


async def resolve_victory(db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]) -> int:
    """Generate loot, mark the incident resolved, and award XP. Returns caps for the batch payout."""
    incident.loot = incident_math.generate_loot(incident.difficulty, incident.type)
    incident.resolve(success=True)

    caps_earned = incident.loot.get("caps", 0)
    await award_combat_xp(db_session, incident, dwellers)

    logger.info(f"Incident {incident.id} resolved successfully! Loot: {incident.loot}")
    incident_publishing.record_event(
        db_session, incident, "resolved", f"{get_incident_definition(incident.type).progress_label}."
    )
    return caps_earned


async def process_incident(db_session: AsyncSession, incident: Incident, seconds_passed: int) -> IncidentRoundResult:
    """Process one round of an active incident (apply damage, check victory)."""
    if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
        return IncidentRoundResult(skipped=True)

    # Get dwellers in affected room with equipment preloaded (N+1 optimization)
    dwellers = list(await crud_dweller.get_healthy_adults_in_room(db_session, incident.room_id))
    if not dwellers:
        return await no_defender_outcome(db_session, incident)

    # Fire is a containment operation: responders suppress a hazard rather
    # than defeat enemies. Other types retain the combat loop.
    dweller_power = incident_math.dweller_combat_power(dwellers)
    threat_power = incident_math.raider_power(incident.difficulty)
    if incident.type == IncidentType.FIRE:  # TODO: make it more generic
        damage_to_dwellers = incident_math.fire_damage(threat_power, seconds_passed)
        response_progress = incident_math.fire_suppression(dweller_power, threat_power, seconds_passed)
        damage_to_raiders = 0.0
    else:
        damage_to_dwellers = incident_math.damage_to_dwellers(threat_power, seconds_passed)
        response_progress = incident_math.damage_to_raiders(dweller_power, seconds_passed) / threat_power
        damage_to_raiders = response_progress * threat_power

    damaged_count, deaths_count = await apply_damage(db_session, incident, dwellers, damage_to_dwellers)
    total_damage = max(0, int(damage_to_dwellers))

    # Track total damage dealt by raiders
    incident.damage_dealt += total_damage

    # Track enemies defeated — accumulate fractional kills so weak defenders
    # still make progress instead of stalling at int() == 0 every tick.
    enemies_this_tick = 0
    if threat_power > 0:
        previous_kills = incident.enemies_defeated
        incident.combat_progress += response_progress
        if incident.type != IncidentType.FIRE:
            incident.enemies_defeated = int(incident.combat_progress)
        enemies_this_tick = incident.enemies_defeated - previous_kills

    # Check victory condition (defeated enough raiders based on difficulty)
    expected_raider_count = incident.difficulty * 2  # Each difficulty = 2 raiders

    if incident.type == IncidentType.FIRE and response_progress > 0:  # TODO: Not hardcoded, must be a system for this
        incident_publishing.record_event(
            db_session,
            incident,
            "containment",
            f"Fire containment increased by {max(1, int(response_progress * 100))}%.",
            {"target": "hazard", "amount": response_progress},
        )
    else:
        incident_publishing.record_event(
            db_session,
            incident,
            "round",
            f"Responders dealt {int(damage_to_raiders)} damage; took {total_damage}.",
            {"target": "combat", "damage_to_dwellers": total_damage, "damage_to_threat": damage_to_raiders},
        )

    resolved = (
        incident.combat_progress >= 1
        if incident.type == IncidentType.FIRE
        else incident.enemies_defeated >= expected_raider_count
    )
    caps_earned = 0
    if resolved:
        caps_earned = await resolve_victory(db_session, incident, dwellers)

    db_session.add(incident)
    await db_session.commit()
    # Death notifications parked by mark_as_dead(commit=False) deliver only
    # once the round actually persisted.
    await notification_service.deliver_deferred_notifications(db_session)

    if resolved:
        await incident_publishing.notify_resolution(db_session, incident, success=True, caps_earned=caps_earned)
        await incident_publishing.publish_sse(incident, "incident_resolved", success=True, caps_earned=caps_earned)

    return IncidentRoundResult(
        damage_to_dwellers=damage_to_dwellers,
        damage_to_raiders=damage_to_raiders,
        dwellers_damaged=damaged_count,
        dwellers_killed=deaths_count,
        enemies_defeated=enemies_this_tick,
        caps_earned=caps_earned,
    )


async def award_combat_xp(db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]) -> None:
    """Award experience to dwellers who participated in combat.

    Args:
        db_session: Database session
        incident: Resolved incident
        dwellers: List of dwellers who fought
    """

    if not dwellers:
        return

    from app.services.leveling_service import leveling_service

    # Base XP from difficulty
    base_xp = incident.difficulty * game_config.combat.xp_per_difficulty

    # Check for perfect combat (no damage taken)
    perfect_combat = incident.damage_dealt == 0

    if perfect_combat:
        base_xp = int(base_xp * game_config.combat.perfect_bonus_multiplier)

    # Distribute XP among participants
    xp_per_dweller = base_xp // len(dwellers)

    for dweller in dwellers:
        dweller.experience = max(0, dweller.experience + xp_per_dweller)
        db_session.add(dweller)

        # Check for level-up
        await leveling_service.check_level_up(db_session, dweller)
