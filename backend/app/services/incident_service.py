"""Incident service for managing combat events and vault disasters."""

import logging
import random

from pydantic import UUID4
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.incident import incident_crud
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.notification import NotificationPriority, NotificationType
from app.models.room import Room
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum
from app.schemas.incident import IncidentRoundResult
from app.schemas.incident_sse import IncidentSseEvent
from app.services.notification_service import notification_service
from app.services.stream_manager import sse_manager
from app.utils.combat import total_combat_power
from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

_INCIDENT_NAMES: dict[IncidentType, str] = {
    IncidentType.FIRE: "🔥 Fire",
    IncidentType.RADROACH_INFESTATION: "🪳 Radroach Infestation",
    IncidentType.RAIDER_ATTACK: "💀 Raider Attack",
    IncidentType.DEATHCLAW_ATTACK: "👹 Deathclaw Attack",
    IncidentType.MOLE_RAT_ATTACK: "🐀 Mole Rat Attack",
    IncidentType.FERAL_GHOUL_ATTACK: "🧟 Feral Ghoul Attack",
    IncidentType.RADSCORPION_ATTACK: "🦂 Radscorpion Attack",
}


class IncidentService:
    """Service for managing vault incidents and combat."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def should_spawn_incident(
        self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int, game_state: GameState | None = None
    ) -> bool:
        """Determine if an incident should spawn based on vault state and time.

        Args:
            db_session: Database session
            vault_id: The vault ID to check
            seconds_passed: Seconds since last tick
            game_state: Optional game state for online/offline check

        Returns:
            bool: True if incident should spawn
        """
        # Check if user is online (has recent activity) - suppress incidents when offline
        if game_state and not game_state.is_user_online(timeout_seconds=600):
            self.logger.debug(f"Vault {vault_id} is offline, suppressing incident spawn")
            return False

        from app.models.vault import Vault

        vault = await db_session.get(Vault, vault_id)
        if vault is not None and vault.incidents_disabled:
            self.logger.debug(f"Incidents are disabled for vault {vault_id}")
            return False

        # Need minimum population
        from app.models.dweller import Dweller

        dwellers_query = select(Dweller).where(Dweller.vault_id == vault_id)
        dwellers_result = await db_session.execute(dwellers_query)
        dweller_count = len(dwellers_result.scalars().all())

        if dweller_count < game_config.incident.min_vault_population:
            return False

        # Check if max active incidents reached
        from app.crud.incident import incident_crud

        active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
        if len(active_incidents) >= game_config.incident.max_active_incidents:
            return False

        # Check cooldown period (if there are any incidents, check the most recent one)
        if active_incidents:
            from datetime import datetime

            most_recent = max(active_incidents, key=lambda i: i.start_time)
            seconds_since_last = (datetime.utcnow() - most_recent.start_time).total_seconds()
            if seconds_since_last < game_config.incident.spawn_cooldown_seconds:
                return False

        # Time-based cap: limit spawn chance growth to prevent bursts
        # Cap hours_passed to prevent excessive spawn chance after long offline periods
        hours_passed = min(seconds_passed / 3600, 2.0)  # Cap at 2 hours worth of chance
        spawn_chance = game_config.incident.spawn_chance_per_hour * hours_passed

        # Random roll
        return random.random() < spawn_chance

    async def spawn_incident(
        self, db_session: AsyncSession, vault_id: UUID4, incident_type: IncidentType | None = None
    ) -> Incident | None:
        """Spawn a new incident in a random occupied room.
        Raiders and Deathclaws spawn at vault door (0,0) and spread inward.

        Rules enforced:
        - Only one incident type per vault at a time
        - Only one incident per room
        - Never spawn in elevators

        Args:
            db_session: Database session
            vault_id: ID of the vault
            incident_type: Type of incident (radscorpion if None)

        Returns:
            Incident or None if no suitable room found
        """
        if not await self._try_acquire_spawn_lock(db_session, vault_id):
            return None

        from app.models.vault import Vault

        vault = await db_session.get(Vault, vault_id)
        if vault is None:
            return None
        if vault.incidents_disabled:
            from app.utils.exceptions import IncidentsDisabledException

            raise IncidentsDisabledException

        active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
        if len(active_incidents) >= game_config.incident.max_active_incidents:
            from app.utils.exceptions import ResourceConflictException

            raise ResourceConflictException(
                detail=f"Vault is at the active-incident cap ({game_config.incident.max_active_incidents})."
            )

        active_types = {incident.type for incident in active_incidents}

        # Runtime spawns use radscorpions; explicit types remain available to
        # administrative and test callers.
        if incident_type is None:
            incident_type = IncidentType.RADSCORPION_ATTACK

        # If type specified but vault has different type, don't spawn
        if active_types and incident_type not in active_types:
            self.logger.info(f"Cannot spawn {incident_type} in vault {vault_id} - vault already has {active_types}")
            return None

        # Get rooms that already have active incidents
        rooms_with_incidents = await incident_crud.get_rooms_with_active_incidents(db_session, vault_id)

        # Determine where to spawn based on incident type
        if incident_type.value in game_config.incident.vault_door_incidents:
            # External attacks spawn at vault door (0,0) and spread inward
            vault_door_query = select(Room).where(
                (Room.vault_id == vault_id) & (Room.coordinate_x == 0) & (Room.coordinate_y == 0)
            )
            vault_door_result = await db_session.execute(vault_door_query)
            target_room = vault_door_result.scalar_one_or_none()

            if not target_room:
                self.logger.warning(f"No vault door found at (0,0) for {incident_type} in vault {vault_id}")
                return None

            # Check if vault door already has incident
            if target_room.id in rooms_with_incidents:
                self.logger.info(f"Vault door already has active incident in vault {vault_id}")
                return None
        else:
            # Other incidents spawn in random occupied rooms (excluding elevators)
            rooms_query = (
                select(Room)
                .join(Dweller, Room.id == Dweller.room_id)
                .where(
                    (Room.vault_id == vault_id)
                    & (Dweller.room_id.is_not(None))
                    & (Room.name != "Elevator")  # Exclude elevators
                )
                .distinct()
            )
            rooms_result = await db_session.execute(rooms_query)
            occupied_rooms = list(rooms_result.scalars().all())

            # Filter out rooms that already have incidents
            available_rooms = [room for room in occupied_rooms if room.id not in rooms_with_incidents]

            if not available_rooms:
                self.logger.warning(
                    f"No available rooms for incident spawn in vault {vault_id} "
                    f"(all occupied non-elevator rooms already have incidents)"
                )
                return None

            # Pick random room
            target_room = random.choice(available_rooms)

        difficulty = random.randint(*game_config.incident.get_difficulty_range(incident_type))

        # Create incident
        incident = await incident_crud.create(
            db_session,
            vault_id=vault_id,
            room_id=target_room.id,
            incident_type=incident_type,
            difficulty=difficulty,
            duration=game_config.incident.spread_duration,
        )

        self.logger.info(
            f"Spawned {incident_type} (difficulty {difficulty}) in room {target_room.name} of vault {vault_id}"
        )

        # Send notification (non-critical, don't break incident creation on failure)
        incident_name = _INCIDENT_NAMES.get(incident_type, str(incident_type))
        await notification_service.notify_owner(
            db_session,
            vault_id,
            context=f"combat_started incident={incident.id} vault={vault_id}",
            sender=lambda user_id: notification_service.create_and_send(
                db_session,
                user_id=user_id,
                vault_id=vault_id,
                notification_type=NotificationType.COMBAT_STARTED,
                priority=NotificationPriority.HIGH,
                title=f"Incident: {incident_name}",
                message=f"{incident_name} in {target_room.name}! Send dwellers to defend.",
                meta_data={
                    "incident_id": str(incident.id),
                    "room_id": str(target_room.id),
                    "room_name": target_room.name,
                    "incident_type": incident_type.value,
                    "difficulty": difficulty,
                },
            ),
        )

        try:
            await sse_manager.publish(
                incident.vault_id,
                "incidents",
                IncidentSseEvent(
                    event_id=str(incident.id),
                    type="incident_spawned",
                    incident_id=str(incident.id),
                    vault_id=str(incident.vault_id),
                    incident_type=incident.type,
                    status=incident.status,
                    room_id=str(target_room.id) if target_room else None,
                    room_name=target_room.name if target_room else None,
                    difficulty=incident.difficulty,
                ).model_dump(),
            )
        except Exception:
            self.logger.exception(
                "Failed to publish SSE incident_spawned: incident_id=%s, vault_id=%s",
                incident.id,
                vault_id,
            )

        return incident

    async def process_incident(
        self, db_session: AsyncSession, incident: Incident, seconds_passed: int
    ) -> IncidentRoundResult:
        """Process an active incident (apply damage, check victory conditions).

        Args:
            db_session: Database session
            incident: The incident to process
            seconds_passed: Time since last tick

        Returns:
            dict with combat results
        """
        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            return IncidentRoundResult(skipped=True)

        transitioned = False

        # Get dwellers in affected room with equipment preloaded (N+1 optimization)
        from sqlalchemy.orm import selectinload

        dwellers_query = (
            select(Dweller)
            .options(
                selectinload(Dweller.weapon),
                selectinload(Dweller.outfit),
            )
            .where(
                (Dweller.room_id == incident.room_id)
                & (Dweller.health > 0)
                & Dweller.is_adult
                & (Dweller.age_group == AgeGroupEnum.ADULT)
            )
        )
        dwellers_result = await db_session.execute(dwellers_query)
        dwellers = list(dwellers_result.scalars().all())

        if not dwellers:
            if (
                incident.elapsed_time() >= incident.duration
                and incident.spread_count < game_config.incident.max_spread_count
                and await self._spread_incident(db_session, incident)
            ):
                await db_session.commit()
                await self._publish_event(incident, "incident_spreading")
                return IncidentRoundResult(no_defenders=True)

            if (
                incident.spread_count >= game_config.incident.max_spread_count
                or incident.elapsed_time() >= incident.duration
            ):
                incident.resolve(success=False)
                db_session.add(incident)
                await db_session.commit()
                await self._publish_event(incident, "incident_resolved", success=False)
                await self._notify_resolution(db_session, incident, success=False)
            return IncidentRoundResult(no_defenders=True)

        # Calculate combat power
        dweller_power = self._calculate_dweller_combat_power(dwellers)
        raider_power = self._calculate_raider_power(incident.difficulty)

        # Apply damage over time
        damage_to_dwellers = self._calculate_damage_to_dwellers(raider_power, seconds_passed)
        damage_to_raiders = self._calculate_damage_to_raiders(dweller_power, seconds_passed)

        # Apply damage to dwellers
        damaged_count = 0
        deaths_count = 0
        total_damage = max(0, int(damage_to_dwellers))
        damage_per_dweller, remainder = divmod(total_damage, len(dwellers))
        for index, dweller in enumerate(dwellers):
            dweller_damage = damage_per_dweller + (1 if index < remainder else 0)
            new_health = max(0, dweller.health - dweller_damage)

            if incident.type == IncidentType.RADSCORPION_ATTACK and dweller_damage > 1:
                radiation_damage = min(dweller_damage - 1, dweller_damage // 2)
                dweller.radiation = min(1_000, dweller.radiation + radiation_damage)
                db_session.add(dweller)

            if new_health != dweller.health:
                # Direct update - SQLAlchemy session tracks the object, no need to refresh
                dweller.health = new_health
                db_session.add(dweller)
                damaged_count += 1

                # Check for death from incident
                if new_health <= 0 and not dweller.is_dead:
                    from app.schemas.common import DeathCauseEnum
                    from app.services.death_service import death_service

                    await death_service.mark_as_dead(db_session, dweller, DeathCauseEnum.INCIDENT)
                    deaths_count += 1
                    self.logger.info(f"Dweller {dweller.first_name} {dweller.last_name} died during incident")

        # Track total damage dealt by raiders
        incident.damage_dealt += total_damage

        # Track enemies defeated — accumulate fractional kills so weak defenders
        # still make progress instead of stalling at int() == 0 every tick.
        if raider_power > 0:
            previous_kills = incident.enemies_defeated
            incident.combat_progress += damage_to_raiders / raider_power
            incident.enemies_defeated = int(incident.combat_progress)
            enemies_this_tick = incident.enemies_defeated - previous_kills
        else:
            enemies_this_tick = 0

        # Check victory condition (defeated enough raiders based on difficulty)
        expected_raider_count = incident.difficulty * 2  # Each difficulty = 2 raiders
        caps_earned = 0

        if incident.enemies_defeated >= expected_raider_count:
            # Victory! Generate loot and resolve
            transitioned = True
            incident.loot = self._generate_loot(incident.difficulty, incident.type)
            incident.resolve(success=True)

            # Track caps for batch vault update (done at game loop level)
            caps_earned = incident.loot.get("caps", 0)

            # Award XP to participating dwellers
            await self._award_combat_xp(db_session, incident, dwellers)

            self.logger.info(f"Incident {incident.id} resolved successfully! Loot: {incident.loot}")

        db_session.add(incident)
        await db_session.commit()

        if transitioned:
            await self._notify_resolution(db_session, incident, success=True, caps_earned=caps_earned)
            await self._publish_event(incident, "incident_resolved", success=True)

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
                    self.logger.error(f"Error processing incident {incident.id}: {e}", exc_info=True)

            if total_caps_earned > 0:
                from app.crud.vault import vault as vault_crud

                vault = await vault_crud.get(db_session, vault_id)
                if vault:
                    await vault_crud.deposit_caps(db_session=db_session, vault_obj=vault, amount=total_caps_earned)
                    stats["caps_earned"] = total_caps_earned
                    self.logger.info(f"Awarded {total_caps_earned} caps to vault {vault_id} from incidents")

        except (SQLAlchemyError, ResourceNotFoundException) as e:
            self.logger.error(f"Error managing incidents for vault {vault_id}: {e}", exc_info=True)
            stats["error"] = str(e)

        return stats

    async def process_all_vaults_incidents(self, db_session: AsyncSession, seconds_passed: int) -> dict:
        """Process incidents for every active vault (fast-tick entry point).

        A PostgreSQL advisory lock serializes execution across workers; the
        transaction is rolled back before releasing it so a failed tick cannot
        leave the session in an aborted state that makes the unlock itself fail.
        """
        if not await self._try_acquire_tick_lock(db_session):
            return {"vaults": 0, "spawned": 0, "resolved": 0}

        from app.models.vault import Vault

        try:
            result = await db_session.execute(select(Vault.id).where(Vault.deleted_at.is_(None)))
            vault_ids = [row[0] for row in result.all()]

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

    async def _try_acquire_spawn_lock(self, db_session: AsyncSession, vault_id: UUID4) -> bool:
        if db_session.get_bind().dialect.name != "postgresql":
            return True

        result = await db_session.execute(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": f"incident-spawn:{vault_id}"},
        )
        return bool(result.scalar())

    async def _notify_resolution(
        self, db_session: AsyncSession, incident: Incident, *, success: bool, caps_earned: int = 0
    ) -> None:
        """Best-effort: notify the owner that an incident was resolved."""
        incident_name = _INCIDENT_NAMES.get(incident.type, str(incident.type))
        if success:
            title = f"Victory: {incident_name}"
            message = f"Your dwellers defeated the attackers and recovered {caps_earned} caps!"
            notification_type = NotificationType.COMBAT_VICTORY
        else:
            title = f"Incident Lost: {incident_name}"
            message = f"Your dwellers failed to contain the {incident_name}."
            notification_type = NotificationType.COMBAT_DEFEAT

        await notification_service.notify_owner(
            db_session,
            incident.vault_id,
            context=f"incident_resolved incident={incident.id} vault={incident.vault_id} success={success}",
            sender=lambda user_id: notification_service.create_and_send(
                db_session,
                user_id=user_id,
                vault_id=incident.vault_id,
                notification_type=notification_type,
                priority=NotificationPriority.HIGH,
                title=title,
                message=message,
                meta_data={
                    "incident_id": str(incident.id),
                    "incident_type": incident.type.value,
                    "loot": incident.loot,
                    "caps_earned": caps_earned,
                },
            ),
        )

    async def get_incident_for_vault(self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4) -> Incident:
        incident = await incident_crud.get(db_session, incident_id)
        if not incident:
            raise ResourceNotFoundException(Incident, incident_id)
        if incident.vault_id != vault_id:
            raise AccessDeniedException("Incident does not belong to this vault")
        return incident

    async def assign_responders(
        self, db_session: AsyncSession, incident: Incident, dweller_ids: list[UUID4]
    ) -> list[UUID4]:
        """Move eligible dwellers into an active incident room before its next round."""
        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            raise ValidationException("Incident is no longer active")

        unique_ids = list(dict.fromkeys(dweller_ids))
        if len(unique_ids) != len(dweller_ids):
            raise ValidationException("Choose each responder only once")

        query = select(Dweller).where(Dweller.id.in_(unique_ids), Dweller.vault_id == incident.vault_id)
        result = await db_session.execute(query)
        dwellers = list(result.scalars().all())
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
        return unique_ids

    async def _spread_incident(self, db_session: AsyncSession, incident: Incident) -> bool:
        """Spread an incident to an adjacent room and report whether it succeeded."""
        if not await self._try_acquire_spawn_lock(db_session, incident.vault_id):
            return False

        if (
            len(await incident_crud.get_active_by_vault(db_session, incident.vault_id))
            >= game_config.incident.max_active_incidents
        ):
            self.logger.info("Incident cap reached while spreading in vault %s", incident.vault_id)
            return False

        # Get the current room to find its coordinates
        current_room_query = select(Room).where(Room.id == incident.room_id)
        current_room_result = await db_session.execute(current_room_query)
        current_room = current_room_result.scalar_one_or_none()

        if not current_room or current_room.coordinate_x is None or current_room.coordinate_y is None:
            return False

        # Get rooms that already have active incidents
        rooms_with_incidents = await incident_crud.get_rooms_with_active_incidents(db_session, incident.vault_id)

        # Find adjacent rooms (within 1-2 coordinate units horizontally or vertically)
        # Exclude elevators and rooms with active incidents
        adjacent_rooms_query = select(Room).where(
            (Room.vault_id == incident.vault_id)
            & (Room.id != incident.room_id)
            & (Room.coordinate_x.is_not(None))
            & (Room.coordinate_y.is_not(None))
            & (Room.name != "Elevator")  # Exclude elevators from spread
            & (
                # Adjacent horizontally (same floor, next to each other)
                (
                    (Room.coordinate_y == current_room.coordinate_y)
                    & (Room.coordinate_x.between(current_room.coordinate_x - 2, current_room.coordinate_x + 2))
                )
                # Adjacent vertically (same column, one floor up/down)
                | (
                    (Room.coordinate_x == current_room.coordinate_x)
                    & (Room.coordinate_y.between(current_room.coordinate_y - 1, current_room.coordinate_y + 1))
                )
            )
        )
        adjacent_rooms_result = await db_session.execute(adjacent_rooms_query)
        all_adjacent_rooms = list(adjacent_rooms_result.scalars().all())

        # Filter out rooms that already have incidents
        adjacent_rooms = [room for room in all_adjacent_rooms if room.id not in rooms_with_incidents]

        if adjacent_rooms:
            # Pick a random adjacent room
            new_room = random.choice(adjacent_rooms)

            # Create a new incident in the adjacent room with the SAME type, capped
            # at the model's max difficulty so it can't snowball on repeat spreads.
            new_incident = await incident_crud.create(
                db_session,
                vault_id=incident.vault_id,
                room_id=new_room.id,
                incident_type=incident.type,  # Same type! (field is called 'type')
                difficulty=min(incident.difficulty + 1, 10),  # Slightly harder
                duration=game_config.incident.spread_duration,
            )

            # Update original incident spread tracking
            incident.spread_to_room(str(new_room.id))
            db_session.add(incident)

            self.logger.warning(
                f"Incident {incident.type} spread from {current_room.name} to {new_room.name} "
                f"(difficulty {new_incident.difficulty})"
            )
            return True

        return False

    async def _publish_event(self, incident: Incident, event_type: str, success: bool | None = None) -> None:
        """Publish a non-critical incident event."""
        try:
            await sse_manager.publish(
                incident.vault_id,
                "incidents",
                IncidentSseEvent(
                    event_id=str(incident.id),
                    type=event_type,
                    incident_id=str(incident.id),
                    vault_id=str(incident.vault_id),
                    incident_type=incident.type,
                    status=incident.status,
                    room_id=str(incident.room_id) if incident.room_id else None,
                    room_name=None,
                    difficulty=incident.difficulty,
                    success=success,
                ).model_dump(),
            )
        except Exception:
            self.logger.exception(
                "Failed to publish SSE %s: incident_id=%s, vault_id=%s",
                event_type,
                incident.id,
                incident.vault_id,
            )

    def _calculate_dweller_combat_power(self, dwellers: list[Dweller]) -> float:
        """Calculate total combat power of dwellers."""
        return total_combat_power(dwellers)

    def _calculate_raider_power(self, difficulty: int) -> float:
        """Calculate raider power based on difficulty."""
        return difficulty * game_config.combat.base_raider_power

    def _calculate_damage_to_dwellers(self, raider_power: float, seconds: int) -> float:
        """Calculate damage dealt to dwellers per tick."""
        # Damage reduced by number of dwellers (distributed)
        damage_per_second = raider_power / 10  # Raiders deal 10% of their power per second
        return damage_per_second * seconds

    def _calculate_damage_to_raiders(self, dweller_power: float, seconds: int) -> float:
        """Calculate damage dealt to raiders per tick."""
        damage_per_second = dweller_power / 5  # Dwellers deal 20% of their power per second
        return damage_per_second * seconds

    async def _award_combat_xp(self, db_session: AsyncSession, incident: "Incident", dwellers: list["Dweller"]) -> None:
        """Award experience to dwellers who participated in combat.

        Args:
            db_session: Database session
            incident: Resolved incident
            dwellers: List of dwellers who fought
        """
        from app.services.leveling_service import leveling_service

        if not dwellers:
            return

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

    def _generate_loot(self, difficulty: int, incident_type: IncidentType) -> dict:
        """Generate loot rewards based on difficulty and incident type."""
        caps = random.randint(
            game_config.combat.loot_caps_min + (difficulty - 1) * game_config.combat.loot_caps_max_per_difficulty // 2,
            game_config.combat.loot_caps_min + difficulty * game_config.combat.loot_caps_max_per_difficulty,
        )

        # Internal threats (fire, radroach, mole rat, radscorpion) give caps only
        # External threats (raider, deathclaw, feral ghoul) give caps + items
        internal_threats = {
            IncidentType.FIRE,
            IncidentType.RADROACH_INFESTATION,
            IncidentType.MOLE_RAT_ATTACK,
            IncidentType.RADSCORPION_ATTACK,
        }

        if incident_type in internal_threats:
            # Internal threats: caps only, no items
            return {"caps": caps, "items": []}

        # External threats: caps + weapons/junk based on difficulty
        items = []
        if difficulty >= 7:
            items.append({"type": "weapon", "rarity": "rare", "name": "Heavy Raider Rifle"})
        elif difficulty >= 4:
            items.append({"type": "weapon", "rarity": "uncommon", "name": "Raider Pistol"})
        else:
            items.append({"type": "junk", "name": "Scrap Metal", "quantity": random.randint(1, 3)})

        return {"caps": caps, "items": items}


# Global instance
incident_service = IncidentService()
