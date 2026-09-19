"""Incident round engine: defender-less outcomes, damage, victory, and XP."""

import logging
from typing import TYPE_CHECKING, cast

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.dweller import dweller as crud_dweller
from app.models.dweller import Dweller
from app.models.incident import Incident, IncidentStatus, IncidentType, get_incident_definition, hazard_team_for
from app.options.identity_modifiers import identity_modifiers_for
from app.schemas.incident import IncidentRoundResult
from app.services.combat import incident_math, incident_publishing
from app.services.combat.incident_spawning import spread_incident
from app.services.contamination_team_service import TEAM_HAZARD_RESIST, TEAM_RESPONSE_BONUS
from app.services.notification_service import notification_service
from app.services.radiation_service import apply_radiation_gain
from app.utils.equipped import equipped_outfit
from app.utils.hazard_resist import outfit_fire_resist

if TYPE_CHECKING:
    from app.models.outfit import Outfit

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
    db_session: AsyncSession,
    incident: Incident,
    dwellers: list[Dweller],
    damage_to_dwellers: float,
    active_member_ids: frozenset[UUID4] = frozenset(),
) -> tuple[int, int, int]:
    """Distribute incoming damage across responders; deaths stay pending for the round commit.

    Returns (damaged_count, deaths_count, damage_taken): the third value is what the
    responders actually took after their response perk, so callers report the same
    number the health bars moved by — and a fully mitigated round reads as zero.
    """
    from app.core.enums import DeathCauseEnum
    from app.services.family.death_service import death_service

    damaged_count = 0
    deaths_count = 0
    damage_taken = 0
    incoming_damage = max(0, int(damage_to_dwellers))
    damage_per_dweller, remainder = divmod(incoming_damage, len(dwellers))
    is_fire = incident.type == IncidentType.FIRE
    for index, dweller in enumerate(dwellers):
        dweller_damage = damage_per_dweller + (1 if index < remainder else 0)
        response_pct = identity_modifiers_for(dweller).incident_response_pct
        if response_pct:
            dweller_damage = int(dweller_damage * (1.0 - response_pct))
        if is_fire:
            # equipped_outfit mirrors radiation_service: no lazy IO, and a
            # missing relationship simply means no protection.
            fire_resist = outfit_fire_resist(cast("Outfit | None", equipped_outfit(dweller)))
            if fire_resist:
                dweller_damage = int(dweller_damage * (1.0 - fire_resist))
        is_active_member = active_member_ids and getattr(dweller, "id", None) in active_member_ids
        if is_active_member:
            dweller_damage = int(dweller_damage * (1.0 - TEAM_HAZARD_RESIST))
        damage_taken += dweller_damage
        new_health = max(0, dweller.health - dweller_damage)

        if (
            incident.type == IncidentType.RADSCORPION_ATTACK and dweller_damage > 1
        ):  # TODO: should depend on enemy type, not incident type, need to think through
            radiation_damage = min(dweller_damage - 1, dweller_damage // 2)
            if is_active_member:
                radiation_damage = int(radiation_damage * (1.0 - TEAM_HAZARD_RESIST))
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

    return damaged_count, deaths_count, damage_taken


async def resolve_victory(db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]) -> int:
    """Generate loot, hand it to the vault, mark the incident resolved, and award XP."""
    from app.crud import storage as crud_storage
    from app.services.loot_overflow_service import loot_overflow_service
    from app.services.reward_service import reward_service
    from app.utils.exceptions import ResourceConflictException

    incident.loot = incident_math.generate_loot(incident.difficulty, incident.type)
    incident.resolve(success=True)

    caps_earned = incident.loot.get("caps", 0)
    storage = await loot_overflow_service.storage_for(db_session, incident.vault_id)
    available_space = await crud_storage.get_available_space(db_session, storage.id) if storage else 0
    granted, held = loot_overflow_service.grant_or_hold(incident.loot.get("items", []), available_space)

    stored_items: list[dict] = []
    for item in granted:
        try:
            await reward_service.grant_item(db_session, incident.vault_id, item)
        except ResourceConflictException:
            # A full vault must not turn a win into a stuck incident: the fight
            # still resolves and the item waits for a take/sell decision.
            held.append(item)
            continue
        stored_items.append(item)
    incident.loot = {**incident.loot, "items": stored_items}
    incident.unclaimed_loot = held
    if held:
        incident_publishing.record_event(
            db_session,
            incident,
            "overflow",
            f"Storage full — {len(held)} item(s) held for your decision.",
        )

    experience_earned = await award_combat_xp(db_session, incident, dwellers)
    incident.loot = {**incident.loot, "experience": experience_earned}

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

    # Credit the round's defenders before any damage lands; the ledger and any
    # team place it earns ride this round's single commit, so a failed round
    # leaves no participation behind.
    from app.services.contamination_team_service import contamination_team_service

    team_result = await contamination_team_service.record_participation(db_session, incident, dwellers)

    # Active members of the team matching this incident's hazard respond with
    # extra power and take less damage; bench/reserve members get nothing.
    team = hazard_team_for(incident.type)
    active_ids = team_result.active_ids

    # Fire is a containment operation: responders suppress a hazard rather
    # than defeat enemies. Other types retain the combat loop.
    dweller_power = incident_math.dweller_combat_power(dwellers)
    if active_ids:
        dweller_power = int(dweller_power * (1 + TEAM_RESPONSE_BONUS * len(active_ids)))
    threat_power = incident_math.raider_power(incident.difficulty)
    if incident.type == IncidentType.FIRE:  # TODO: make it more generic
        damage_to_dwellers = incident_math.fire_damage(threat_power, seconds_passed)
        response_progress = incident_math.fire_suppression(dweller_power, threat_power, seconds_passed)
        damage_to_raiders = 0.0
    else:
        damage_to_dwellers = incident_math.damage_to_dwellers(threat_power, seconds_passed)
        response_progress = incident_math.damage_to_raiders(dweller_power, seconds_passed) / threat_power
        damage_to_raiders = response_progress * threat_power

    damaged_count, deaths_count, total_damage = await apply_damage(
        db_session, incident, dwellers, damage_to_dwellers, active_member_ids=active_ids
    )

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
    # Incident level-ups parked the same way: emit and notify post-commit.
    from app.services.leveling_service import leveling_service

    await leveling_service.deliver_deferred_level_ups(db_session)

    if resolved:
        experience_earned = (incident.loot or {}).get("experience", 0)
        await incident_publishing.notify_resolution(
            db_session, incident, success=True, caps_earned=caps_earned, experience_earned=experience_earned
        )
        await incident_publishing.publish_sse(
            incident, "incident_resolved", success=True, caps_earned=caps_earned, experience_earned=experience_earned
        )

    # Auto-equip runs last, after the round committed: outfit_crud.equip commits
    # internally, so it must not ride the round's transaction. It also recovers
    # from a failed equip with a rollback, which expires loaded instances — so
    # nothing may read the round's ORM objects once this has run.
    if team and team_result.active_gainers:
        await contamination_team_service.equip_hazard_outfits(
            db_session, incident.vault_id, team_result.active_gainers, team
        )

    return IncidentRoundResult(
        damage_to_dwellers=damage_to_dwellers,
        damage_to_raiders=damage_to_raiders,
        dwellers_damaged=damaged_count,
        dwellers_killed=deaths_count,
        enemies_defeated=enemies_this_tick,
        caps_earned=caps_earned,
    )


async def award_combat_xp(db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]) -> int:
    """Award experience to dwellers who participated in combat.

    Args:
        db_session: Database session
        incident: Resolved incident
        dwellers: List of dwellers who fought

    Returns:
        Total experience granted across responders.
    """

    if not dwellers:
        return 0

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

        # Check for level-up; the notification parks until the round commits
        # and drains deferred deliveries (see process_incident).
        leveled_up, levels_gained = await leveling_service.check_level_up(db_session, dweller)
        if leveled_up:
            await leveling_service.settle_level_up(
                db_session,
                dweller,
                old_level=dweller.level - levels_gained,
                levels_gained=levels_gained,
                commit=False,
            )

    return xp_per_dweller * len(dwellers)
