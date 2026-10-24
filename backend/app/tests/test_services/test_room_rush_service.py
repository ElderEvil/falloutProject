from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.core.event_bus import GameEvent
from app.core.game_config import game_config
from app.crud.incident import incident_crud
from app.crud.notification import notification as notification_crud
from app.models.incident import IncidentType
from app.models.notification import NotificationType
from app.models.room import Room
from app.models.storage import Storage
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.room_rush_service import (
    RoomRushService,
    _effective_stacks,
    _eligible_incident_types,
    _fail_chance,
    roll_bonus_caps,
)
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.item_factory import build_outfit


class _Rng:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values, 0.0)

    def choice(self, sequence: list[Any]) -> Any:
        return sequence[0]


@pytest_asyncio.fixture
async def rush_setup(async_session: AsyncSession, user_with_vault: tuple) -> dict[str, Any]:
    _, vault = user_with_vault
    vault.power = 50
    vault.power_max = 100
    vault.food = 0
    vault.food_max = 100
    vault.water = 0
    vault.water_max = 100
    vault.bottle_caps = 100
    async_session.add(vault)
    await async_session.commit()

    room = await crud.room.create(
        async_session,
        RoomCreate(
            vault_id=vault.id,
            name="Power Generator",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            output=100,
            size_min=1,
            size_max=3,
            size=1,
            tier=1,
        ),
    )
    worker = await _create_worker(async_session, vault, room, strength=5, luck=5)
    return {"vault": vault, "room": room, "worker": worker}


async def _create_worker(
    async_session: AsyncSession,
    vault: Vault,
    room: Room,
    *,
    strength: int = 1,
    luck: int = 1,
    happiness: int = 50,
) -> Any:
    worker = await crud.dweller.create(
        async_session,
        DwellerCreate(
            vault_id=vault.id,
            first_name="Rush",
            last_name="Worker",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=1,
            experience=0,
            max_health=100,
            health=100,
            radiation=0,
            happiness=happiness,
            strength=strength,
            perception=1,
            endurance=1,
            charisma=1,
            intelligence=1,
            agility=1,
            luck=luck,
        ),
    )
    worker.room_id = room.id
    async_session.add(worker)
    await async_session.commit()
    return worker


def _service() -> RoomRushService:
    return RoomRushService()


@pytest.mark.asyncio
async def test_quote_reports_risk_and_capacity_clamped_payout(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]
    quote = await _service().quote(async_session, room, vault)

    assert quote.can_rush is True
    assert quote.blocked_reason is None
    assert quote.stacks == 0
    assert quote.worker_count == 1
    assert quote.max_stacks == game_config.rush.max_stacks
    assert quote.fail_chance == pytest.approx(_fail_chance(5, 5, 0))
    assert quote.success_chance == pytest.approx(100 - quote.fail_chance)
    assert quote.payout.power > 0
    assert quote.payout.power <= vault.power_max - vault.power


@pytest.mark.asyncio
async def test_quote_blocks_non_production_room(async_session: AsyncSession, rush_setup: dict[str, Any]) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]
    room.category = RoomTypeEnum.MISC
    await async_session.commit()

    quote = await _service().quote(async_session, room, vault)

    assert quote.can_rush is False
    assert quote.blocked_reason == "not_production"


@pytest.mark.asyncio
async def test_quote_blocks_room_without_living_workers(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    worker.is_dead = True
    await async_session.commit()

    quote = await _service().quote(async_session, room, vault)

    assert quote.can_rush is False
    assert quote.blocked_reason == "no_workers"


@pytest.mark.asyncio
async def test_quote_blocks_active_incident(async_session: AsyncSession, rush_setup: dict[str, Any]) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]
    await incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=1,
    )

    quote = await _service().quote(async_session, room, vault)

    assert quote.can_rush is False
    assert quote.blocked_reason == "active_incident"


@pytest.mark.asyncio
async def test_quote_blocks_unpowered_non_strength_room(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]
    vault.power = 0
    room.ability = SPECIALEnum.AGILITY
    await async_session.commit()

    quote = await _service().quote(async_session, room, vault)

    assert quote.can_rush is False
    assert quote.blocked_reason == "no_power"


@pytest.mark.asyncio
async def test_rush_success_applies_payout_caps_xp_happiness_and_stack(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    starting_power = vault.power
    starting_caps = vault.bottle_caps

    result = await _service().rush(async_session, room, vault, rng=_Rng(0.9, 0.0, 0.0))

    assert result.outcome == "success"
    assert result.stacks_after == 1
    assert result.payout.power > 0
    assert vault.power == starting_power + result.payout.power
    assert result.caps == (200 + room.tier) * room.segment_count * 6
    assert vault.bottle_caps == starting_caps + result.caps
    assert result.xp_per_worker == game_config.rush.xp_per_worker
    assert worker.experience == game_config.rush.xp_per_worker
    assert worker.happiness == 60
    assert vault.happiness == 60
    assert room.rush_stacks == 1
    assert room.last_rush_at is not None


@pytest.mark.asyncio
async def test_rush_failure_spawns_incident_in_rushed_room(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    worker.happiness = 50
    await async_session.commit()

    result = await _service().rush(async_session, room, vault, rng=_Rng(0.1))

    assert result.outcome == "failure"
    assert result.stacks_after == 1
    assert result.payout.power == 0
    assert result.xp_per_worker == 0
    assert result.incident_id is not None
    assert result.incident_type == IncidentType.FIRE.value
    incident = await incident_crud.get(async_session, result.incident_id)
    assert incident is not None
    assert incident.room_id == room.id
    assert worker.happiness == 40
    assert vault.happiness == 40
    assert room.rush_stacks == 1


@pytest.mark.asyncio
async def test_rush_failure_with_incidents_disabled_still_penalises(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    vault.incidents_disabled = True
    await async_session.commit()

    result = await _service().rush(async_session, room, vault, rng=_Rng(0.1))

    assert result.outcome == "failure"
    assert result.incident_id is None
    assert result.incident_type is None
    assert worker.happiness == 40
    assert room.rush_stacks == 1


def test_effective_stacks_decay_and_cap() -> None:
    now = datetime.utcnow()
    room = Room.model_construct(rush_stacks=3, last_rush_at=now - timedelta(seconds=1200))
    assert _effective_stacks(room, now) == 1

    room = Room.model_construct(rush_stacks=6, last_rush_at=now - timedelta(seconds=1200 * 10))
    assert _effective_stacks(room, now) == 0

    room = Room.model_construct(rush_stacks=6, last_rush_at=now)
    assert _effective_stacks(room, now) == 6


def test_caps_roll_uses_room_tier_and_width() -> None:
    caps = roll_bonus_caps(avg_luck=10, room_tier=3, room_width=2, rng=_Rng(0.0, 0.0))
    assert caps == (200 + 3) * 2 * 6

    assert roll_bonus_caps(avg_luck=0, room_tier=1, room_width=1, rng=_Rng(0.0, 0.0)) == 0
    assert roll_bonus_caps(avg_luck=10, room_tier=1, room_width=1, rng=_Rng(1.0)) == 0


def test_fail_chance_floor_and_stack_penalty() -> None:
    assert _fail_chance(10, 10, 0) == pytest.approx(10.0)
    assert _fail_chance(1, 1, 0) == pytest.approx(37.0)
    assert _fail_chance(10, 10, 3) == pytest.approx(40.0)
    assert _fail_chance(10, 10, 6) == pytest.approx(70.0)
    assert _fail_chance(50, 50, 6) == pytest.approx(70.0)


def test_effective_stacks_decay_ten_minutes_per_stack_and_never_negative() -> None:
    now = datetime.utcnow()
    assert _effective_stacks(Room.model_construct(rush_stacks=2, last_rush_at=now - timedelta(minutes=10)), now) == 1
    assert _effective_stacks(Room.model_construct(rush_stacks=2, last_rush_at=now - timedelta(minutes=59)), now) == 0
    assert _effective_stacks(Room.model_construct(rush_stacks=6, last_rush_at=None), now) == 6
    assert _effective_stacks(Room.model_construct(rush_stacks=6, last_rush_at=now - timedelta(days=30)), now) == 0


def test_eligible_incident_types_follow_rush_thresholds() -> None:
    assert _eligible_incident_types(1) == [IncidentType.FIRE]
    assert _eligible_incident_types(8) == [IncidentType.FIRE, IncidentType.RADROACH_INFESTATION]
    assert _eligible_incident_types(30) == [
        IncidentType.FIRE,
        IncidentType.RADROACH_INFESTATION,
        IncidentType.MOLE_RAT_ATTACK,
    ]
    assert _eligible_incident_types(50) == [
        IncidentType.FIRE,
        IncidentType.RADROACH_INFESTATION,
        IncidentType.MOLE_RAT_ATTACK,
        IncidentType.RADSCORPION_ATTACK,
    ]


@pytest.mark.asyncio
async def test_quote_uses_effective_stat_with_outfit_bonus(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    before = await _service().quote(async_session, room, vault)

    worker.outfit = build_outfit({"name": "Lucky Suit", "luck": 3}, RarityEnum.COMMON)
    async_session.add(worker)
    await async_session.commit()

    after = await _service().quote(async_session, room, vault)
    assert after.avg_luck == pytest.approx(before.avg_luck + 3)
    assert after.fail_chance < before.fail_chance


@pytest.mark.asyncio
async def test_success_pays_medical_storage_up_to_capacity(async_session: AsyncSession, user_with_vault: tuple) -> None:
    _, vault = user_with_vault
    vault.power = 50
    vault.power_max = 100
    async_session.add(vault)
    await async_session.commit()
    room = await crud.room.create(
        async_session,
        RoomCreate(
            vault_id=vault.id,
            name="Medbay",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.INTELLIGENCE,
            capacity=5,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            output=100,
            size_min=1,
            size_max=3,
            size=1,
            tier=1,
        ),
    )
    worker = await _create_worker(async_session, vault, room, strength=1, luck=1)
    worker.intelligence = 10
    async_session.add(worker)
    storage = Storage(vault_id=vault.id, stimpack=4)
    async_session.add(storage)
    await async_session.commit()

    result = await _service().rush(async_session, room, vault, rng=_Rng(0.9, 1.0))

    assert result.outcome == "success"
    assert result.payout.stimpack == 1
    assert result.payout.radaway == 0
    await async_session.refresh(storage)
    assert storage.stimpack == 5


@pytest.mark.asyncio
async def test_success_happiness_clamps_to_ceiling(async_session: AsyncSession, rush_setup: dict[str, Any]) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    worker.happiness = 95
    await async_session.commit()

    result = await _service().rush(async_session, room, vault, rng=_Rng(0.9, 1.0))

    assert result.outcome == "success"
    assert worker.happiness == 100
    assert vault.happiness == 100


@pytest.mark.asyncio
async def test_failure_happiness_clamps_to_floor(async_session: AsyncSession, rush_setup: dict[str, Any]) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    worker.happiness = 5
    await async_session.commit()

    result = await _service().rush(async_session, room, vault, rng=_Rng(0.0))

    assert result.outcome == "failure"
    assert worker.happiness == 10
    assert vault.happiness == 10


@pytest.mark.asyncio
async def test_failure_without_spawnable_incident_still_penalises(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    worker.happiness = 50
    await async_session.commit()

    with patch(
        "app.services.room_rush_service.incident_spawning.spawn_incident",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await _service().rush(async_session, room, vault, rng=_Rng(0.0))

    assert result.outcome == "failure"
    assert result.incident_id is None
    assert result.incident_type is None
    assert worker.happiness == 40
    assert room.rush_stacks == 1


@pytest.mark.asyncio
async def test_rush_rejects_non_production_room(async_session: AsyncSession, rush_setup: dict[str, Any]) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]
    room.category = RoomTypeEnum.MISC
    await async_session.commit()

    with pytest.raises(ValidationException):
        await _service().rush(async_session, room, vault, rng=_Rng(0.9))


@pytest.mark.asyncio
async def test_rush_rejects_room_without_workers(async_session: AsyncSession, rush_setup: dict[str, Any]) -> None:
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    worker.is_dead = True
    await async_session.commit()

    with pytest.raises(ResourceConflictException):
        await _service().rush(async_session, room, vault, rng=_Rng(0.9))


@pytest.mark.asyncio
async def test_rush_rejects_active_incident(async_session: AsyncSession, rush_setup: dict[str, Any]) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]
    await incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=1,
    )

    with pytest.raises(ResourceConflictException):
        await _service().rush(async_session, room, vault, rng=_Rng(0.9))


@pytest.mark.asyncio
async def test_rush_rejects_unpowered_non_strength_room(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]
    vault.power = 0
    room.ability = SPECIALEnum.AGILITY
    await async_session.commit()

    with pytest.raises(ValidationException):
        await _service().rush(async_session, room, vault, rng=_Rng(0.9))


@pytest.mark.asyncio
async def test_rush_returns_conflict_when_room_lock_is_held(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]

    with (
        patch(
            "app.services.room_rush_service.db_locks.try_advisory_xact_lock",
            new_callable=AsyncMock,
            return_value=False,
        ),
        pytest.raises(ResourceConflictException),
    ):
        await _service().rush(async_session, room, vault, rng=_Rng(0.9))


@pytest.mark.asyncio
async def test_two_rushes_serialize_and_never_overflow_resource_caps(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]
    starting_power = vault.power

    first = await _service().rush(async_session, room, vault, rng=_Rng(0.9, 1.0))
    second = await _service().rush(async_session, room, vault, rng=_Rng(0.9, 1.0))

    assert first.stacks_after == 1
    assert second.stacks_after == 2
    assert first.payout.power == vault.power_max - starting_power
    assert second.payout.power == 0
    assert vault.power == vault.power_max
    assert room.rush_stacks == 2


@pytest.mark.asyncio
async def test_success_sends_notification_and_emits_post_commit_events(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]

    with patch("app.services.room_rush_service.event_bus.emit", new_callable=AsyncMock) as emit:
        result = await _service().rush(async_session, room, vault, rng=_Rng(0.9, 1.0))

    assert result.outcome == "success"
    notification = next(
        notification
        for notification in await notification_crud.get_user_notifications(async_session, vault.user_id)
        if notification.notification_type == NotificationType.RUSH_SUCCEEDED
    )
    assert notification.meta_data is not None
    assert notification.meta_data["event"] == "room_rush"
    assert notification.meta_data["outcome"] == "success"
    assert notification.meta_data["room_id"] == str(room.id)
    assert notification.meta_data["incident_id"] is None

    emitted = [call.args[0] for call in emit.await_args_list]
    assert GameEvent.RESOURCE_COLLECTED in emitted
    assert GameEvent.RUSH_SUCCEEDED in emitted


@pytest.mark.asyncio
async def test_failure_sends_notification_with_incident_metadata(
    async_session: AsyncSession, rush_setup: dict[str, Any]
) -> None:
    vault, room = rush_setup["vault"], rush_setup["room"]

    with patch("app.services.room_rush_service.event_bus.emit", new_callable=AsyncMock) as emit:
        result = await _service().rush(async_session, room, vault, rng=_Rng(0.0))

    assert result.outcome == "failure"
    notification = next(
        notification
        for notification in await notification_crud.get_user_notifications(async_session, vault.user_id)
        if notification.notification_type == NotificationType.RUSH_FAILED
    )
    assert notification.meta_data is not None
    assert notification.meta_data["outcome"] == "failure"
    assert notification.meta_data["incident_id"] == str(result.incident_id)

    emitted = [call.args[0] for call in emit.await_args_list]
    assert GameEvent.RUSH_FAILED in emitted
    assert GameEvent.RESOURCE_COLLECTED not in emitted
