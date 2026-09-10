"""Incident service for managing combat events and vault disasters."""

import logging

from pydantic import UUID4
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgeGroupEnum, DwellerStatusEnum
from app.core.game_config import game_config
from app.crud.dweller import dweller as crud_dweller
from app.crud.incident import incident_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.incident import Incident, IncidentStatus, IncidentType, get_incident_definition
from app.schemas.incident import IncidentRead, IncidentRoundResult
from app.services.combat import incident_math, incident_publishing, incident_reads, incident_spawning
from app.services.notification_service import notification_service
from app.services.radiation_service import apply_radiation_gain
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)


class IncidentService:
    """Service for managing vault incidents and combat."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _record_event(
        db_session: AsyncSession, incident: Incident, kind: str, message: str, data: dict | None = None
    ) -> None:
        """Append a meaningful lifecycle event; callers commit with their state change."""
        incident_publishing.record_event(db_session, incident, kind=kind, message=message, data=data)

    async def get_incident_read(
        self, db_session: AsyncSession, incident: Incident, room_name: str | None
    ) -> IncidentRead:
        """Build the stable, type-aware incident contract consumed by the UI."""
        return await incident_reads.get_incident_read(db_session, incident, room_name)

    async def should_spawn_incident(
        self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int, game_state: GameState | None = None
    ) -> bool:
        """Spawn gating — see incident_spawning."""
        return await incident_spawning.should_spawn_incident(db_session, vault_id, seconds_passed, game_state)

    async def spawn_incident(
        self, db_session: AsyncSession, vault_id: UUID4, incident_type: IncidentType | None = None
    ) -> Incident | None:
        """Spawn orchestration — see incident_spawning."""
        return await incident_spawning.spawn_incident(db_session, vault_id, incident_type)

    async def _no_defender_outcome(self, db_session: AsyncSession, incident: Incident) -> IncidentRoundResult:
        """An active incident nobody responds to: spread it, keep waiting, or lose it."""
        if (
            incident.elapsed_time() >= incident.duration
            and incident.spread_count < game_config.incident.max_spread_count
            and await self._spread_incident(db_session, incident)
        ):
            await db_session.commit()
            await incident_publishing.publish_sse(incident, "incident_spreading")
            return IncidentRoundResult(no_defenders=True)

        if (
            incident.spread_count >= game_config.incident.max_spread_count
            or incident.elapsed_time() >= incident.duration
        ):
            incident.resolve(success=False)
            self._record_event(
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

    async def _apply_damage(
        self, db_session: AsyncSession, incident: Incident, dwellers: list[Dweller], damage_to_dwellers: float
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
                    self.logger.info(f"Dweller {dweller.first_name} {dweller.last_name} died during incident")

        return damaged_count, deaths_count

    async def _resolve_victory(self, db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]) -> int:
        """Generate loot, mark the incident resolved, and award XP. Returns caps for the batch payout."""
        incident.loot = incident_math.generate_loot(incident.difficulty, incident.type)
        incident.resolve(success=True)

        caps_earned = incident.loot.get("caps", 0)
        await self._award_combat_xp(db_session, incident, dwellers)

        self.logger.info(f"Incident {incident.id} resolved successfully! Loot: {incident.loot}")
        self._record_event(
            db_session, incident, "resolved", f"{get_incident_definition(incident.type).progress_label}."
        )
        return caps_earned

    async def process_incident(
        self, db_session: AsyncSession, incident: Incident, seconds_passed: int
    ) -> IncidentRoundResult:
        """Process one round of an active incident (apply damage, check victory)."""
        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            return IncidentRoundResult(skipped=True)

        # Get dwellers in affected room with equipment preloaded (N+1 optimization)
        dwellers = list(await crud_dweller.get_healthy_adults_in_room(db_session, incident.room_id))
        if not dwellers:
            return await self._no_defender_outcome(db_session, incident)

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

        damaged_count, deaths_count = await self._apply_damage(db_session, incident, dwellers, damage_to_dwellers)
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

        if (
            incident.type == IncidentType.FIRE and response_progress > 0
        ):  # TODO: Not hardcoded, must be a system for this
            self._record_event(
                db_session,
                incident,
                "containment",
                f"Fire containment increased by {max(1, int(response_progress * 100))}%.",
                {"target": "hazard", "amount": response_progress},
            )
        else:
            self._record_event(
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
            caps_earned = await self._resolve_victory(db_session, incident, dwellers)

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

    async def process_vault_incidents(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        seconds_passed: int,
        game_state: GameState | None = None,
    ) -> dict:
        """Process one vault's incidents: spawn check, combat rounds, spreading, caps.

        Runs on its own fast tick (``incident_tick`` actor), independent of the
        60-second game loop, so combat gives live feedback.
        """
        stats = {"spawned": 0, "processed": 0, "resolved": 0, "active_count": 0, "caps_earned": 0}

        try:
            if game_state is None:
                game_state = await db_session.get(GameState, vault_id)

            from app.models.vault import Vault

            vault = await db_session.get(Vault, vault_id)
            if vault is not None and vault.incidents_disabled:
                return stats

            active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
            stats["active_count"] = len(active_incidents)

            if game_state and game_state.is_paused:
                return stats

            # Incidents do not punish players for time away from the vault.
            if game_state and not game_state.is_user_online():
                return stats

            if await self.should_spawn_incident(db_session, vault_id, seconds_passed, game_state):
                new_incident = await self.spawn_incident(db_session, vault_id)
                if new_incident:
                    stats["spawned"] = 1
                    self.logger.info(f"Spawned new incident {new_incident.type} in vault {vault_id}")

            total_caps_earned = 0

            for incident in active_incidents:
                try:
                    result = await self.process_incident(
                        db_session, incident, min(seconds_passed, game_config.game_loop.tick_interval)
                    )

                    if result.skipped:
                        continue

                    stats["processed"] += 1

                    if result.caps_earned > 0:
                        total_caps_earned += result.caps_earned

                    await db_session.refresh(incident)
                    if incident.status.value in ("resolved", "failed"):
                        stats["resolved"] += 1
                        self.logger.info(f"Incident {incident.id} auto-resolved with status {incident.status}")

                except (SQLAlchemyError, ValueError, RuntimeError) as e:
                    notification_service.discard_deferred_notifications(db_session)
                    self.logger.error(f"Error processing incident {incident.id}: {e}", exc_info=True)

            if total_caps_earned > 0:
                from app.crud.vault import vault as vault_crud
                from app.services.vault_service import vault_service

                vault = await vault_crud.get(db_session, vault_id)
                if vault:
                    await vault_service.deposit_caps(db_session=db_session, vault_obj=vault, amount=total_caps_earned)
                    stats["caps_earned"] = total_caps_earned
                    self.logger.info(f"Awarded {total_caps_earned} caps to vault {vault_id} from incidents")

        except (SQLAlchemyError, ResourceNotFoundException) as e:  # TODO: Should it be here?
            self.logger.error(f"Error managing incidents for vault {vault_id}: {e}", exc_info=True)
            stats["error"] = str(e)

        return stats

    async def process_all_vaults_incidents(
        self, db_session: AsyncSession, seconds_passed: int
    ) -> dict:  # TODO: Must be tested for performance
        """Process incidents for every active vault (fast-tick entry point).

        A PostgreSQL advisory lock serializes execution across workers; the
        transaction is rolled back before releasing it so a failed tick cannot
        leave the session in an aborted state that makes the unlock itself fail.
        """
        if not await self._try_acquire_tick_lock(db_session):
            return {"vaults": 0, "spawned": 0, "resolved": 0}

        try:
            vaults = await vault_crud.get_active_ordered(db_session)
            vault_ids = [vault.id for vault in vaults]

            totals = {"vaults": len(vault_ids), "spawned": 0, "resolved": 0}
            for vault_id in vault_ids:
                stats = await self.process_vault_incidents(db_session, vault_id, seconds_passed)
                totals["spawned"] += stats["spawned"]
                totals["resolved"] += stats["resolved"]
        except Exception:
            # The session is in a failed state after an error; roll back so the
            # advisory unlock below can run on a healthy transaction.
            await db_session.rollback()
            raise
        else:
            return totals
        finally:
            await self._release_tick_lock(db_session)

    async def _try_acquire_tick_lock(self, db_session: AsyncSession) -> bool:
        if db_session.get_bind().dialect.name != "postgresql":
            return True

        result = await db_session.execute(
            text("SELECT pg_try_advisory_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": "incident-tick"},
        )
        return bool(result.scalar())

    async def _release_tick_lock(self, db_session: AsyncSession) -> None:
        if db_session.get_bind().dialect.name != "postgresql":
            return
        try:
            await db_session.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))"),
                {"lock_key": "incident-tick"},
            )
        except Exception:
            # Unlock failure must not mask the original tick error or stall the
            # worker; the advisory lock self-releases on session close anyway.
            self.logger.exception("Failed to release incident tick advisory lock")

    async def get_incident_for_vault(self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4) -> Incident:
        return await incident_reads.get_incident_for_vault(db_session, incident_id, vault_id)

    async def assign_responders(
        self, db_session: AsyncSession, incident: Incident, dweller_ids: list[UUID4]
    ) -> list[UUID4]:
        """Move eligible dwellers into an active incident room before its next round."""
        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            raise ValidationException("Incident is no longer active")

        unique_ids = list(dict.fromkeys(dweller_ids))
        if len(unique_ids) != len(dweller_ids):
            raise ValidationException("Choose each responder only once")

        dwellers = list(await crud_dweller.get_by_ids_in_vault(db_session, unique_ids, incident.vault_id))
        if len(dwellers) != len(unique_ids):
            raise ValidationException("One or more responders do not belong to this vault")

        unavailable = [
            dweller
            for dweller in dwellers
            if not dweller.is_adult
            or dweller.age_group != AgeGroupEnum.ADULT
            or dweller.health <= 0
            or dweller.is_dead
            or dweller.status in {DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING, DwellerStatusEnum.DEAD}
        ]
        if unavailable:
            raise ValidationException("Only healthy adult dwellers in the vault can respond")

        from app.services.dweller_service import dweller_service

        for dweller in dwellers:
            await dweller_service.update_dweller(db_session, dweller.id, {"room_id": incident.room_id})
        self._record_event(db_session, incident, "responders_assigned", f"{len(unique_ids)} responder(s) assigned.")
        await db_session.commit()
        return unique_ids

    async def _spread_incident(self, db_session: AsyncSession, incident: Incident) -> bool:
        """Spread orchestration — see incident_spawning."""
        return await incident_spawning.spread_incident(db_session, incident)

    async def _award_combat_xp(self, db_session: AsyncSession, incident: "Incident", dwellers: list[Dweller]) -> None:
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


# Global instance
incident_service = IncidentService()
