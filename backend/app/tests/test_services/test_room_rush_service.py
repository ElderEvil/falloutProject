from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, IncidentType, NotificationType, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.core.event_bus import GameEvent
from app.core.game_config import game_config
from app.crud.incident import incident_crud
from app.crud.notification import notification as notification_crud
from app.models.room import Room
from app.models.storage import Storage
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.combat.incident_service import incident_service
from app.services.room_rush_service import (
    RoomRushService,
    _effective_stacks,
    _eligible_incident_types,
    _fail_chance,
    roll_bonus_caps,
    room_rush_service,
)
from app.services.vault.scenario_service import SHORT_RATIONS_SCENARIO
from app.tests.factory.dwellers import create_rush_dweller_payload
from app.tests.factory.rooms import create_rush_room_payload
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.item_factory import build_outfit
from app.utils.time import utcnow

FIRE, ROACH, MOLE, SCORPION = (
    IncidentType.FIRE,
    IncidentType.RADROACH_INFESTATION,
    IncidentType.MOLE_RAT_ATTACK,
    IncidentType.RADSCORPION_ATTACK,
)


class _Rng:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values, 0.0)

    def choice(self, sequence: list[Any]) -> Any:
        return sequence[0]


async def _worker(async_session, vault, room, **stats):
    worker = await crud.dweller.create(
        async_session, DwellerCreate(vault_id=vault.id, **create_rush_dweller_payload(**stats))
    )
    worker.room_id = room.id
    async_session.add(worker)
    await async_session.commit()
    return worker


async def _room(async_session, vault, **room_kw):
    return await crud.room.create(async_session, RoomCreate(vault_id=vault.id, **create_rush_room_payload(**room_kw)))


async def _medbay(async_session, user_with_vault, *, stimpack=None):
    _, vault = user_with_vault
    vault.power, vault.power_max = 50, 100
    async_session.add(vault)
    await async_session.commit()
    room = await _room(async_session, vault, name="Medbay", ability=SPECIALEnum.INTELLIGENCE, capacity=5)
    await _worker(async_session, vault, room, intelligence=10)
    storage = None
    if stimpack is not None:
        storage = Storage(vault_id=vault.id, stimpack=stimpack)
        async_session.add(storage)
        await async_session.commit()
    return vault, room, storage


async def _low_output_room(async_session, user_with_vault):
    _, vault = user_with_vault
    vault.power, vault.power_max = 50, 100
    async_session.add(vault)
    await async_session.commit()
    room = await _room(async_session, vault, output=1)
    await _worker(async_session, vault, room, strength=1)
    return vault, room


@pytest_asyncio.fixture
async def rush_setup(async_session, user_with_vault):
    _, vault = user_with_vault
    vault.power, vault.power_max = 50, 100
    vault.food = vault.water = 0
    vault.food_max = vault.water_max = 100
    vault.bottle_caps = 100
    async_session.add(vault)
    await async_session.commit()
    room = await _room(async_session, vault)
    return {"vault": vault, "room": room, "worker": await _worker(async_session, vault, room, strength=5, luck=5)}


async def _quote(session, setup):
    return await room_rush_service.quote(session, setup["room"], setup["vault"])


async def _rush(session, setup, *rolls):
    return await room_rush_service.rush(session, setup["room"], setup["vault"], rng=_Rng(*rolls))


async def _mutate(session, setup, mutations):
    for target, attr, value in mutations:
        setattr(setup[target], attr, value)
    await session.commit()


async def _break_incident(session, setup):
    await incident_crud.create(
        session, vault_id=setup["vault"].id, room_id=setup["room"].id, incident_type=IncidentType.FIRE, difficulty=1
    )


# name, mutations, extra breaker, blocked reason, exception raised by rush
BLOCKS = [
    ("misc", [("room", "category", RoomTypeEnum.MISC)], None, "not_production", ValidationException),
    ("dead", [("worker", "is_dead", True)], None, "no_workers", ResourceConflictException),
    (
        "exploring",
        [("worker", "status", DwellerStatusEnum.EXPLORING)],
        None,
        "no_workers",
        ResourceConflictException,
    ),
    ("incident", [], _break_incident, "active_incident", ResourceConflictException),
    (
        "unpowered",
        [("vault", "power", 0), ("room", "ability", SPECIALEnum.AGILITY)],
        None,
        "no_power",
        ValidationException,
    ),
]


async def _apply_block(session, setup, mutations, breaker):
    if mutations:
        await _mutate(session, setup, mutations)
    if breaker:
        await breaker(session, setup)


async def test_quote_reports_risk_and_capacity_clamped_payout(async_session, rush_setup):
    vault = rush_setup["vault"]
    storage = Storage(vault_id=vault.id, stimpack=3)
    async_session.add(storage)
    await async_session.commit()
    quote = await _quote(async_session, rush_setup)
    assert (quote.can_rush, quote.blocked_reason, quote.stacks, quote.worker_count) == (True, None, 0, 1)
    assert quote.max_stacks == game_config.rush.max_stacks
    assert quote.fail_chance == pytest.approx(_fail_chance(5, 5, 0))
    assert quote.success_chance == pytest.approx(100 - quote.fail_chance)
    assert 0 < quote.payout.power <= vault.power_max - vault.power
    assert (vault.power, vault.food, vault.water) == (50, 0, 0)
    assert storage.stimpack == 3
    assert vault not in async_session.dirty
    assert storage not in async_session.dirty


async def test_short_rations_scales_rush_quote_and_payout(async_session, rush_setup):
    vault, room = rush_setup["vault"], rush_setup["room"]
    room.name, room.ability = "Diner", SPECIALEnum.AGILITY
    await async_session.commit()
    ordinary = await _quote(async_session, rush_setup)
    assert ordinary.payout.food > 0
    vault.scenario_key = SHORT_RATIONS_SCENARIO
    await async_session.commit()
    reduced = await _quote(async_session, rush_setup)
    assert 0 < reduced.payout.food < ordinary.payout.food
    result = await _rush(async_session, rush_setup, 0.9, 1.0)
    assert result.outcome == "success"
    assert result.payout.food == reduced.payout.food
    assert vault.food == reduced.payout.food


@pytest.mark.parametrize(("name", "mutations", "breaker", "reason", "exc"), BLOCKS)
async def test_quote_blocks_room(async_session, rush_setup, name, mutations, breaker, reason, exc):
    await _apply_block(async_session, rush_setup, mutations, breaker)
    quote = await _quote(async_session, rush_setup)
    assert quote.can_rush is False
    assert quote.blocked_reason == reason
    if name == "exploring":
        assert quote.worker_count == 0


async def test_rush_success_applies_payout_caps_xp_happiness_and_stack(async_session, rush_setup):
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    starting_power, starting_caps = vault.power, vault.bottle_caps
    result = await _rush(async_session, rush_setup, 0.9, 0.0, 0.0)
    assert (result.outcome, result.stacks_after) == ("success", 1)
    assert result.payout.power > 0
    assert vault.power == starting_power + result.payout.power
    assert result.caps == (200 + room.tier) * room.segment_count * 6
    assert vault.bottle_caps == starting_caps + result.caps
    assert (result.xp_per_worker, worker.experience) == (game_config.rush.xp_per_worker,) * 2
    assert (worker.happiness, vault.happiness) == (60, 60)
    assert (room.rush_stacks, room.last_rush_at is not None) == (1, True)


async def test_rush_failure_spawns_incident_in_rushed_room(async_session, rush_setup):
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    result = await _rush(async_session, rush_setup, 0.1)
    assert (result.outcome, result.stacks_after, result.payout.power, result.xp_per_worker) == ("failure", 1, 0, 0)
    assert result.incident_id is not None
    assert result.incident_type == IncidentType.FIRE.value
    incident = await incident_crud.get(async_session, result.incident_id)
    assert incident is not None
    assert incident.room_id == room.id
    assert (worker.happiness, vault.happiness, room.rush_stacks) == (40, 40, 1)


async def test_rush_failure_with_incidents_disabled_still_penalises(async_session, rush_setup):
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    vault.incidents_disabled = True
    await async_session.commit()
    result = await _rush(async_session, rush_setup, 0.1)
    assert result.outcome == "failure"
    assert (result.incident_id, result.incident_type) == (None, None)
    assert (worker.happiness, room.rush_stacks) == (40, 1)


@pytest.mark.parametrize(
    ("stacks", "age", "expected"),
    [
        (3, timedelta(seconds=1200), 1),
        (6, timedelta(seconds=12000), 0),
        (6, timedelta(0), 6),
        (2, timedelta(minutes=10), 1),
        (2, timedelta(minutes=59), 0),
        (6, None, 6),
        (6, timedelta(days=30), 0),
    ],
)
def test_effective_stacks_decay_and_cap(stacks, age, expected):
    now = utcnow()
    room = Room.model_construct(rush_stacks=stacks, last_rush_at=None if age is None else now - age)
    assert _effective_stacks(room, now) == expected


def test_caps_roll_uses_room_tier_and_width():
    assert roll_bonus_caps(avg_luck=10, room_tier=3, room_width=2, rng=_Rng(0.0, 0.0)) == (200 + 3) * 2 * 6
    assert roll_bonus_caps(avg_luck=0, room_tier=1, room_width=1, rng=_Rng(0.0, 0.0)) == 0
    assert roll_bonus_caps(avg_luck=10, room_tier=1, room_width=1, rng=_Rng(1.0)) == 0


def test_fail_chance_floor_and_stack_penalty():
    assert _fail_chance(10, 10, 0) == pytest.approx(10.0)
    assert _fail_chance(1, 1, 0) == pytest.approx(37.0)
    assert _fail_chance(10, 10, 3) == pytest.approx(40.0)
    assert _fail_chance(10, 10, 6) == pytest.approx(70.0)
    assert _fail_chance(50, 50, 6) == pytest.approx(70.0)


@pytest.mark.parametrize(
    ("threshold", "types"),
    [(1, [FIRE]), (8, [FIRE, ROACH]), (30, [FIRE, ROACH, MOLE]), (50, [FIRE, ROACH, MOLE, SCORPION])],
)
def test_eligible_incident_types_follow_rush_thresholds(threshold, types):
    assert _eligible_incident_types(threshold) == types


async def test_quote_uses_effective_stat_with_outfit_bonus(async_session, rush_setup):
    worker = rush_setup["worker"]
    before = await _quote(async_session, rush_setup)
    worker.outfit = build_outfit({"name": "Lucky Suit", "luck": 3}, RarityEnum.COMMON)
    async_session.add(worker)
    await async_session.commit()
    after = await _quote(async_session, rush_setup)
    assert after.avg_luck == pytest.approx(before.avg_luck + 3)
    assert after.fail_chance < before.fail_chance


async def test_success_pays_medical_storage_up_to_capacity(async_session, user_with_vault):
    vault, room, storage = await _medbay(async_session, user_with_vault, stimpack=4)
    quote = await _quote(async_session, {"vault": vault, "room": room})
    assert quote.payout.stimpack == 1
    await async_session.refresh(storage)
    assert storage.stimpack == 4
    result = await _rush(async_session, {"vault": vault, "room": room}, 0.9, 1.0)
    assert result.outcome == "success"
    assert (result.payout.stimpack, result.payout.radaway) == (1, 0)
    await async_session.refresh(storage)
    assert storage.stimpack == 5


@pytest.mark.parametrize(
    ("happiness", "rolls", "outcome", "clamped"), [(95, (0.9, 1.0), "success", 100), (5, (0.0,), "failure", 10)]
)
async def test_happiness_clamps_to_ceiling_and_floor(async_session, rush_setup, happiness, rolls, outcome, clamped):
    worker = rush_setup["worker"]
    worker.happiness = happiness
    await async_session.commit()
    result = await _rush(async_session, rush_setup, *rolls)
    assert result.outcome == outcome
    assert (worker.happiness, rush_setup["vault"].happiness) == (clamped, clamped)


async def test_failure_without_spawnable_incident_still_penalises(async_session, rush_setup):
    worker, room = rush_setup["worker"], rush_setup["room"]
    with patch(
        "app.services.room_rush_service.incident_spawning.spawn_incident", new_callable=AsyncMock, return_value=None
    ):
        result = await _rush(async_session, rush_setup, 0.0)
    assert result.outcome == "failure"
    assert (result.incident_id, result.incident_type) == (None, None)
    assert (worker.happiness, room.rush_stacks) == (40, 1)


@pytest.mark.parametrize(("name", "mutations", "breaker", "reason", "exc"), [b for b in BLOCKS if b[0] != "exploring"])
async def test_rush_rejects_invalid_room(async_session, rush_setup, name, mutations, breaker, reason, exc):
    await _apply_block(async_session, rush_setup, mutations, breaker)
    with pytest.raises(exc):
        await _rush(async_session, rush_setup, 0.9)


async def test_rush_returns_conflict_when_room_lock_is_held(async_session, rush_setup):
    with (
        patch(
            "app.services.room_rush_service.db_locks.try_advisory_xact_lock",
            new_callable=AsyncMock,
            return_value=False,
        ),
        pytest.raises(ResourceConflictException),
    ):
        await _rush(async_session, rush_setup, 0.9)


async def test_second_rush_at_cap_is_blocked_and_keeps_stacks(async_session, rush_setup):
    vault, room = rush_setup["vault"], rush_setup["room"]
    starting_power = vault.power
    first = await _rush(async_session, rush_setup, 0.9, 1.0)
    assert first.stacks_after == 1
    assert first.payout.power == vault.power_max - starting_power
    assert (vault.power, room.rush_stacks) == (vault.power_max, 1)
    with pytest.raises(ValidationException):
        await _rush(async_session, rush_setup, 0.9, 1.0)
    assert (room.rush_stacks, vault.power) == (1, vault.power_max)


async def test_success_sends_notification_and_emits_post_commit_events(async_session, rush_setup):
    vault, room = rush_setup["vault"], rush_setup["room"]
    with patch("app.services.room_rush_service.event_bus.emit", new_callable=AsyncMock) as emit:
        result = await _rush(async_session, rush_setup, 0.9, 0.0, 0.0)
    assert (result.outcome, result.caps > 0) == ("success", True)
    notification = next(
        n
        for n in await notification_crud.get_user_notifications(async_session, vault.user_id)
        if n.notification_type == NotificationType.RUSH_SUCCEEDED
    )
    assert notification.meta_data is not None
    assert notification.meta_data["event"] == "room_rush"
    assert notification.meta_data["outcome"] == "success"
    assert notification.meta_data["room_id"] == str(room.id)
    assert notification.meta_data["incident_id"] is None
    resource_events = [call for call in emit.await_args_list if call.args[0] == GameEvent.RESOURCE_COLLECTED]
    assert len(resource_events) == 1
    payload = resource_events[0].args[2]
    assert payload["source"] == "rush"
    assert payload["resources"]["power"] == result.payout.power
    assert payload["resources"]["caps"] == result.caps
    assert GameEvent.RUSH_SUCCEEDED in [call.args[0] for call in emit.await_args_list]


async def test_failure_sends_notification_with_incident_metadata(async_session, rush_setup):
    vault = rush_setup["vault"]
    with patch("app.services.room_rush_service.event_bus.emit", new_callable=AsyncMock) as emit:
        result = await _rush(async_session, rush_setup, 0.0)
    assert result.outcome == "failure"
    notification = next(
        n
        for n in await notification_crud.get_user_notifications(async_session, vault.user_id)
        if n.notification_type == NotificationType.RUSH_FAILED
    )
    assert notification.meta_data is not None
    assert notification.meta_data["outcome"] == "failure"
    assert notification.meta_data["incident_id"] == str(result.incident_id)
    emitted = [call.args[0] for call in emit.await_args_list]
    assert GameEvent.RUSH_FAILED in emitted
    assert GameEvent.RESOURCE_COLLECTED not in emitted


async def test_failed_rush_waits_before_incident_ui_and_combat(async_session, rush_setup):
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    before = utcnow()
    result = await RoomRushService().rush(async_session, room, vault, rng=_Rng(0.0))
    incident = await incident_crud.get(async_session, result.incident_id)
    assert incident is not None
    assert incident.start_time >= before + timedelta(seconds=4.2)
    assert (await incident_service.get_active_incident_list(async_session, vault.id)).incident_count == 0
    assert (await RoomRushService().quote(async_session, room, vault)).blocked_reason == "active_incident"
    health = worker.health
    round_result = await incident_service.process_incident(async_session, incident, 2)
    assert round_result.skipped
    assert (worker.health, incident.combat_progress) == (health, 0)
    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    assert all(n.notification_type != NotificationType.COMBAT_STARTED for n in notifications)
    incident.start_time = utcnow() - timedelta(seconds=1)
    async_session.add(incident)
    await async_session.commit()
    await incident_service.process_vault_incidents(async_session, vault.id, 2)
    visible = await incident_service.get_active_incident_list(async_session, vault.id)
    assert visible.incident_count == 1
    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    assert sum(n.notification_type == NotificationType.COMBAT_STARTED for n in notifications) == 1
    await incident_service.process_vault_incidents(async_session, vault.id, 2)
    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    assert sum(n.notification_type == NotificationType.COMBAT_STARTED for n in notifications) == 1


async def test_quote_blocks_when_resources_are_full(async_session, rush_setup):
    # A full vault clamps the payout to zero, so the quote must block the rush (#1455).
    vault, room = rush_setup["vault"], rush_setup["room"]
    vault.power = vault.power_max
    async_session.add(vault)
    await async_session.commit()
    quote = await _quote(async_session, rush_setup)
    assert (quote.can_rush, quote.blocked_reason) == (False, "resources_full")
    assert quote.payout.model_dump() == {"power": 0, "food": 0, "water": 0, "stimpack": 0, "radaway": 0}
    assert (room.rush_stacks, vault.power) == (0, vault.power_max)


async def test_quote_still_quotes_when_headroom_remains(async_session, rush_setup):
    vault = rush_setup["vault"]
    vault.power = vault.power_max - 1
    async_session.add(vault)
    await async_session.commit()
    quote = await _quote(async_session, rush_setup)
    assert (quote.can_rush, quote.blocked_reason, quote.payout.power) == (True, None, 1)


async def test_quote_blocks_when_medical_storage_is_full(async_session, user_with_vault):
    vault, room, storage = await _medbay(async_session, user_with_vault, stimpack=5)
    quote = await _quote(async_session, {"vault": vault, "room": room})
    assert (quote.can_rush, quote.blocked_reason, quote.payout.stimpack) == (False, "resources_full", 0)
    await async_session.refresh(storage)
    assert storage.stimpack == 5


@pytest.mark.parametrize(("reason", "fragment"), [("resources_full", "full"), ("no_yield", "nothing")])
def test_blocked_exception_maps_blocked_reason(reason, fragment):
    exception = RoomRushService._blocked_exception(reason)
    assert isinstance(exception, ValidationException)
    assert fragment in str(exception.detail)


async def test_quote_reports_no_yield_when_payout_rounds_to_zero(async_session, user_with_vault):
    # output 1 * strength 1 * 0.0012 rate * 300s = 0.36 raw power, which rounds to 0.
    vault, room = await _low_output_room(async_session, user_with_vault)
    quote = await _quote(async_session, {"vault": vault, "room": room})
    assert (quote.can_rush, quote.blocked_reason, quote.payout.power) == (False, "no_yield", 0)
    assert (vault.power, room.rush_stacks) == (50, 0)


async def test_quote_reports_no_yield_when_medical_storage_row_missing(async_session, user_with_vault):
    vault, room, _ = await _medbay(async_session, user_with_vault)
    quote = await _quote(async_session, {"vault": vault, "room": room})
    assert (quote.can_rush, quote.blocked_reason, quote.payout.stimpack) == (False, "no_yield", 0)
    assert room.rush_stacks == 0


async def test_rush_at_resource_cap_raises_without_stacks_or_incident(async_session, rush_setup):
    # A quote taken with headroom must not submit after storage filled (#1457).
    vault, room, worker = rush_setup["vault"], rush_setup["room"], rush_setup["worker"]
    quote = await _quote(async_session, rush_setup)
    assert quote.can_rush is True
    vault.power = vault.power_max
    async_session.add(vault)
    await async_session.commit()
    with pytest.raises(ValidationException):
        await _rush(async_session, rush_setup, 0.9, 1.0)
    await async_session.refresh(room)
    assert (room.rush_stacks, room.last_rush_at, vault.power, worker.happiness) == (0, None, vault.power_max, 50)
    assert await incident_crud.get_active_by_vault(async_session, vault.id) == []


async def test_rush_rejects_payout_that_rounds_to_zero(async_session, user_with_vault):
    # Submission enforces the no_yield guard too, before any stack or outcome roll.
    vault, room = await _low_output_room(async_session, user_with_vault)
    with pytest.raises(ValidationException) as exc_info:
        await _rush(async_session, {"vault": vault, "room": room}, 0.9, 1.0)
    assert "nothing" in str(exc_info.value.detail)
    await async_session.refresh(room)
    assert (room.rush_stacks, room.last_rush_at, vault.power) == (0, None, 50)


async def test_rush_with_headroom_succeeds_and_increments_stacks(async_session, rush_setup):
    room = rush_setup["room"]
    quote = await _quote(async_session, rush_setup)
    assert quote.can_rush is True
    assert quote.blocked_reason is None
    result = await _rush(async_session, rush_setup, 0.9, 1.0)
    assert (result.outcome, result.payout.power > 0, result.stacks_after, room.rush_stacks) == (
        "success",
        True,
        1,
        1,
    )
