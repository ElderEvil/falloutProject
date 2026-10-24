"""Room Rush: risk quote and atomic rush action."""

import logging
import math
import random
from datetime import datetime
from types import ModuleType

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import db_locks
from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud.dweller import dweller as crud_dweller
from app.crud.incident import incident_crud
from app.crud.room import room as crud_room
from app.crud.storage import storage as crud_storage
from app.models.dweller import Dweller
from app.models.incident import Incident, IncidentType
from app.models.notification import NotificationPriority, NotificationType
from app.models.room import Room
from app.models.vault import Vault
from app.options.identity_modifiers import effective_stat
from app.schemas.room_rush import RoomRushQuote, RoomRushResourceGain, RoomRushResult, RushBlockedReason
from app.services.combat import incident_spawning
from app.services.notification_service import notification_service
from app.services.resource_manager import ResourceManager, compute_medical_capacity
from app.services.rewards.resources import grant_experience
from app.services.vault_service import vault_service
from app.utils.exceptions import (
    IncidentsDisabledException,
    ResourceConflictException,
    ValidationException,
)
from app.utils.reward_delivery import defer_reward_delivery

logger = logging.getLogger(__name__)

_HAPPINESS_FLOOR = 10
_HAPPINESS_CEILING = 100

_RUSH_INCIDENT_TYPES: dict[str, IncidentType] = {
    "fire": IncidentType.FIRE,
    "radroach": IncidentType.RADROACH_INFESTATION,
    "mole_rat": IncidentType.MOLE_RAT_ATTACK,
    "radscorpion": IncidentType.RADSCORPION_ATTACK,
}


def _caps_chance(avg_luck: float) -> float:
    return min(game_config.rush.caps_luck_chance_cap, game_config.rush.caps_luck_chance_per_point * avg_luck)


def _fail_chance(avg_ability: float, avg_luck: float, stacks: int) -> float:
    base = max(
        game_config.rush.min_fail, game_config.rush.base_fail - game_config.rush.stat_weight * (avg_ability + avg_luck)
    )
    return min(100.0, base + game_config.rush.stack_penalty * stacks)


def _effective_stacks(room: Room, now: datetime) -> int:
    stored = max(0, room.rush_stacks)
    if stored == 0 or room.last_rush_at is None:
        return min(game_config.rush.max_stacks, stored)
    elapsed = max(0.0, (now - room.last_rush_at).total_seconds())
    decayed = math.floor(elapsed / game_config.rush.stack_decay_seconds)
    return max(0, min(game_config.rush.max_stacks, stored - decayed))


def _averages(room: Room, workers: list[Dweller]) -> tuple[float, float]:
    if not workers or room.ability is None:
        return 0.0, 0.0
    ability = room.ability.lower()
    avg_ability = sum(effective_stat(worker, ability) for worker in workers) / len(workers)
    avg_luck = sum(effective_stat(worker, "luck") for worker in workers) / len(workers)
    return avg_ability, avg_luck


def _blocked_reason(
    room: Room, workers: list[Dweller], active_incidents: list[Incident], vault: Vault
) -> RushBlockedReason | None:
    if room.category != RoomTypeEnum.PRODUCTION or room.ability is None or not room.output:
        return "not_production"
    if not workers:
        return "no_workers"
    if active_incidents:
        return "active_incident"
    if vault.power <= 0 and room.ability != SPECIALEnum.STRENGTH:
        return "no_power"
    return None


def _eligible_incident_types(population: int) -> list[IncidentType]:
    eligible: list[IncidentType] = []
    for key, minimum in game_config.rush.incident_min_population.items():
        incident_type = _RUSH_INCIDENT_TYPES.get(key)
        if incident_type is None:
            logger.warning("Ignoring unknown rush incident type %r in configuration", key)
            continue
        if population >= minimum:
            eligible.append(incident_type)
    return eligible


def roll_bonus_caps(avg_luck: float, room_tier: int, room_width: int, rng: ModuleType | random.Random) -> int:
    """Roll the datamined luck-based caps bonus for one successful rush."""
    chance = _caps_chance(avg_luck)
    tiers = game_config.rush.caps_tiers
    if chance <= 0 or not tiers or rng.random() >= chance:
        return 0

    roll = rng.random()
    for threshold, base, multiplier in tiers:
        if roll < threshold:
            return (base + room_tier) * room_width * multiplier
    _, base, multiplier = tiers[-1]
    return (base + room_tier) * room_width * multiplier


class RoomRushService:
    def __init__(self) -> None:
        self.resource_manager = ResourceManager()

    async def quote(self, db_session: AsyncSession, room: Room, vault: Vault) -> RoomRushQuote:
        workers = await self._living_workers(db_session, room.id)
        active_incidents = await incident_crud.get_active_by_vault(db_session, vault.id)
        now = datetime.utcnow()
        stacks = _effective_stacks(room, now)
        avg_ability, avg_luck = _averages(room, workers)
        fail_chance = _fail_chance(avg_ability, avg_luck, stacks)
        population = await crud_dweller.count_living_in_vault(db_session, vault.id)
        blocked_reason = _blocked_reason(room, workers, active_incidents, vault)

        return RoomRushQuote(
            can_rush=blocked_reason is None,
            blocked_reason=blocked_reason,
            fail_chance=fail_chance,
            success_chance=100.0 - fail_chance,
            stacks=stacks,
            max_stacks=game_config.rush.max_stacks,
            avg_ability=avg_ability,
            avg_luck=avg_luck,
            worker_count=len(workers),
            payout=await self._preview_payout(db_session, room, vault, workers),
            caps_chance=_caps_chance(avg_luck) * 100.0,
            eligible_incidents=[]
            if vault.incidents_disabled
            else [incident_type.value for incident_type in _eligible_incident_types(population)],
            next_stack_penalty=0.0 if stacks >= game_config.rush.max_stacks else game_config.rush.stack_penalty,
        )

    async def rush(
        self, db_session: AsyncSession, room: Room, vault: Vault, *, rng: ModuleType | random.Random = random
    ) -> RoomRushResult:
        if not await db_locks.try_advisory_xact_lock(db_session, f"room-rush:{room.id}"):
            raise ResourceConflictException("This room is busy; try again.")

        await db_session.refresh(room)
        await db_session.refresh(vault)
        workers = await self._living_workers(db_session, room.id)
        active_incidents = await incident_crud.get_active_by_vault(db_session, vault.id)
        blocked_reason = _blocked_reason(room, workers, active_incidents, vault)
        if blocked_reason is not None:
            raise self._blocked_exception(blocked_reason)

        now = datetime.utcnow()
        stacks_before = _effective_stacks(room, now)
        avg_ability, avg_luck = _averages(room, workers)
        fail_chance = _fail_chance(avg_ability, avg_luck, stacks_before)
        roll = rng.random()
        failed = roll < fail_chance / 100.0
        stacks_after = min(game_config.rush.max_stacks, stacks_before + 1)
        await crud_room.update_rush_state(db_session, room, stacks=stacks_after, last_rush_at=now, commit=False)
        logger.info(
            "room_rush room=%s vault=%s stacks=%s fail_chance=%.2f roll=%.4f outcome=%s",
            room.id,
            vault.id,
            stacks_before,
            fail_chance,
            roll,
            "failure" if failed else "success",
        )

        async with defer_reward_delivery(db_session):
            if failed:
                result = await self._fail(db_session, room, vault, workers, stacks_after, rng)
            else:
                result = await self._succeed(db_session, room, vault, workers, avg_luck, stacks_after, rng)

        try:
            await db_session.commit()
        except Exception:
            notification_service.discard_deferred_notifications(db_session)
            await db_session.rollback()
            raise

        await notification_service.deliver_deferred_notifications(db_session)
        await self._emit_events(room, vault, result)
        return result

    async def _succeed(
        self,
        db_session: AsyncSession,
        room: Room,
        vault: Vault,
        workers: list[Dweller],
        avg_luck: float,
        stacks_after: int,
        rng: ModuleType | random.Random,
    ) -> RoomRushResult:
        storage = await crud_storage.get_by_vault(db_session, vault.id)
        rooms = await crud_room.get_all_by_vault(db_session, vault.id)
        raw_payout = self.resource_manager.calculate_room_production(room, workers, game_config.rush.payout_seconds)
        applied = self.resource_manager.apply_room_payout(vault, storage, compute_medical_capacity(rooms), raw_payout)
        payout = RoomRushResourceGain(**applied)

        caps = roll_bonus_caps(avg_luck, room.tier, room.segment_count, rng)
        applied_caps = 0
        if caps > 0:
            applied_caps = await vault_service.deposit_caps(
                db_session=db_session,
                vault_obj=vault,
                amount=caps,
                commit=False,
                emit_event=False,
                track_earnings=True,
            )

        await self._apply_happiness(db_session, vault, workers, game_config.rush.happiness_delta)
        xp_per_worker = game_config.rush.xp_per_worker
        await grant_experience(db_session, [worker.id for worker in workers], xp_per_worker)

        await self._notify(
            db_session,
            vault,
            NotificationType.RUSH_SUCCEEDED,
            title="Room Rush Succeeded",
            message=f"The rush paid off with {self._payout_summary(payout)}.",
            room=room,
            outcome="success",
            payout=payout,
            caps=applied_caps,
            incident=None,
        )
        next_fail_chance = _fail_chance(*_averages(room, workers), stacks_after)
        return RoomRushResult(
            outcome="success",
            payout=payout,
            caps=applied_caps,
            xp_per_worker=xp_per_worker,
            happiness_delta=game_config.rush.happiness_delta,
            incident_id=None,
            incident_type=None,
            stacks_after=stacks_after,
            next_fail_chance=next_fail_chance,
            message=f"The rush succeeded and produced {self._payout_summary(payout)}.",
        )

    async def _fail(
        self,
        db_session: AsyncSession,
        room: Room,
        vault: Vault,
        workers: list[Dweller],
        stacks_after: int,
        rng: ModuleType | random.Random,
    ) -> RoomRushResult:
        await self._apply_happiness(db_session, vault, workers, -game_config.rush.happiness_delta)
        incident = await self._spawn_failure_incident(db_session, room, vault, rng)
        payout = RoomRushResourceGain()

        message = "The rush backfired, but the room escaped a disaster."
        if incident is not None:
            message = f"The rush backfired and triggered {incident.type.value.replace('_', ' ')}."
            logger.warning("Rush failure spawned %s in room %s", incident.type.value, room.id)

        await self._notify(
            db_session,
            vault,
            NotificationType.RUSH_FAILED,
            title="Room Rush Failed",
            message=message,
            room=room,
            outcome="failure",
            payout=payout,
            caps=0,
            incident=incident,
        )
        next_fail_chance = _fail_chance(*_averages(room, workers), stacks_after)
        return RoomRushResult(
            outcome="failure",
            payout=payout,
            caps=0,
            xp_per_worker=0,
            happiness_delta=-game_config.rush.happiness_delta,
            incident_id=incident.id if incident is not None else None,
            incident_type=incident.type.value if incident is not None else None,
            stacks_after=stacks_after,
            next_fail_chance=next_fail_chance,
            message=message,
        )

    async def _spawn_failure_incident(
        self,
        db_session: AsyncSession,
        room: Room,
        vault: Vault,
        rng: ModuleType | random.Random,
    ) -> Incident | None:
        if vault.incidents_disabled:
            logger.warning("Rush failure for room %s skipped an incident: incidents are disabled", room.id)
            return None

        population = await crud_dweller.count_living_in_vault(db_session, vault.id)
        eligible = _eligible_incident_types(population)
        if not eligible:
            logger.warning("Rush failure for room %s had no eligible incident type", room.id)
            return None

        incident_type = rng.choice(eligible)
        difficulty_bonus = (room.tier - 1) * game_config.rush.difficulty_per_tier + (
            room.segment_count - 1
        ) * game_config.rush.difficulty_per_segment
        try:
            incident = await incident_spawning.spawn_incident(
                db_session,
                vault.id,
                incident_type,
                target_room_id=room.id,
                difficulty_bonus=difficulty_bonus,
                start_delay_seconds=game_config.rush.incident_start_delay_seconds,
            )
        except (IncidentsDisabledException, ResourceConflictException) as exc:
            logger.warning("Rush failure could not spawn an incident for room %s: %s", room.id, exc.detail)
            return None

        if incident is None:
            logger.warning("Rush failure could not spawn an incident for room %s", room.id)
        return incident

    async def _preview_payout(
        self, db_session: AsyncSession, room: Room, vault: Vault, workers: list[Dweller]
    ) -> RoomRushResourceGain:
        storage = await crud_storage.get_by_vault(db_session, vault.id)
        rooms = await crud_room.get_all_by_vault(db_session, vault.id)
        raw_payout = self.resource_manager.calculate_room_production(room, workers, game_config.rush.payout_seconds)
        applied = self.resource_manager.apply_room_payout(
            vault.model_copy(),
            storage.model_copy() if storage is not None else None,
            compute_medical_capacity(rooms),
            raw_payout,
        )
        return RoomRushResourceGain(**applied)

    async def _living_workers(self, db_session: AsyncSession, room_id: UUID4) -> list[Dweller]:
        assigned = await crud_dweller.get_by_room(db_session, room_id, with_equipment=True)
        return [worker for worker in assigned if not worker.is_dead]

    async def _apply_happiness(
        self, db_session: AsyncSession, vault: Vault, workers: list[Dweller], delta: int
    ) -> None:
        # Retail spreads the change over ~30s; this repo has no temporary-happiness
        # buff system, so the delta is applied immediately and documented as a deviation.
        for worker in workers:
            worker.happiness = max(_HAPPINESS_FLOOR, min(_HAPPINESS_CEILING, worker.happiness + delta))
            db_session.add(worker)
        await db_session.flush()

        living = await crud_dweller.get_living_in_vault(db_session, vault.id)
        if living:
            vault.happiness = round(sum(dweller.happiness for dweller in living) / len(living))
            db_session.add(vault)

    async def _notify(
        self,
        db_session: AsyncSession,
        vault: Vault,
        notification_type: NotificationType,
        *,
        title: str,
        message: str,
        room: Room,
        outcome: str,
        payout: RoomRushResourceGain,
        caps: int,
        incident: Incident | None,
    ) -> None:
        if vault.user_id is None:
            return
        await notification_service.create_and_send(
            db_session,
            vault.user_id,
            notification_type,
            title,
            message,
            vault_id=vault.id,
            priority=NotificationPriority.NORMAL,
            meta_data={
                "event": "room_rush",
                "outcome": outcome,
                "room_id": str(room.id),
                "incident_id": str(incident.id) if incident is not None else None,
                "incident_type": incident.type.value if incident is not None else None,
                "payout": payout.model_dump(),
                "caps": caps,
            },
            commit=False,
        )

    async def _emit_events(self, room: Room, vault: Vault, result: RoomRushResult) -> None:
        if result.outcome == "success":
            resources = {
                resource_type: amount for resource_type, amount in result.payout.model_dump().items() if amount > 0
            }
            if resources:
                await event_bus.emit(
                    GameEvent.RESOURCE_COLLECTED,
                    vault.id,
                    {"resources": resources, "source": "rush"},
                )
            if result.caps > 0:
                await event_bus.emit(
                    GameEvent.RESOURCE_COLLECTED,
                    vault.id,
                    {"resource_type": "caps", "amount": result.caps},
                )

        event_type = GameEvent.RUSH_SUCCEEDED if result.outcome == "success" else GameEvent.RUSH_FAILED
        await event_bus.emit(
            event_type,
            vault.id,
            {
                "room_id": str(room.id),
                "outcome": result.outcome,
                "caps": result.caps,
                "resources": result.payout.model_dump(),
                "source": "rush",
            },
        )

    @staticmethod
    def _payout_summary(payout: RoomRushResourceGain) -> str:
        parts = [f"{amount} {resource_type}" for resource_type, amount in payout.model_dump().items() if amount > 0]
        return ", ".join(parts) if parts else "no resources"

    @staticmethod
    def _blocked_exception(reason: RushBlockedReason) -> Exception:
        if reason in ("not_production", "no_power"):
            return ValidationException("This room cannot be rushed.")
        if reason == "active_incident":
            return ResourceConflictException("Resolve the active incident before rushing.")
        return ResourceConflictException("Assign a living dweller to this room before rushing.")


room_rush_service = RoomRushService()
