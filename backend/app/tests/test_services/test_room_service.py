from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import IncidentStatus, IncidentType, RoomTypeEnum, SPECIALEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_data import get_static_game_data
from app.models.incident import Incident
from app.models.room import Room
from app.models.team import Team, TeamMember
from app.models.training import Training
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.room_assignment_policy import calculate_room_capacity
from app.services.room_remodel_service import remodel_room
from app.services.room_service import room_service
from app.services.vault import seeding
from app.services.vault_service import vault_service
from app.tests.factory.dwellers import create_rush_dweller_payload
from app.tests.test_services._transaction_helpers import counting_commit
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceConflictException,
    ResourceNotFoundException,
    UniqueRoomViolationException,
    VaultOperationException,
)
from app.utils.room_rules import room_refund
from app.utils.time import utcnow

RECALC = "app.services.vault_service.vault_service.recalculate_vault_attributes"
LOCK = "app.services.room_assignment_policy.db_locks.hold_advisory_lock"

ROOM_DEFAULTS: dict[str, Any] = {
    "name": "Power Generator",
    "category": RoomTypeEnum.PRODUCTION,
    "ability": SPECIALEnum.STRENGTH,
    "population_required": None,
    "base_cost": 100,
    "incremental_cost": 25,
    "t2_upgrade_cost": 500,
    "t3_upgrade_cost": 1500,
    "capacity": None,
    "output": None,
    "size_min": 3,
    "size_max": 9,
    "size": 3,
    "tier": 1,
    "coordinate_x": 0,
    "coordinate_y": 1,
    "image_url": None,
    "capacity_formula": "10*S",
    "output_formula": "5*S",
}


def _payload(vault_id: UUID, **overrides: Any) -> RoomCreate:
    return RoomCreate(vault_id=vault_id, **(ROOM_DEFAULTS | overrides))


def _pc(vault: Vault, **overrides: Any) -> RoomCreate:
    return _payload(vault.id, **overrides)


ELEVATOR: dict[str, Any] = {
    "name": "Elevator",
    "category": RoomTypeEnum.MISC,
    "ability": None,
    "incremental_cost": None,
    "t2_upgrade_cost": None,
    "t3_upgrade_cost": None,
    "size_min": 1,
    "size_max": 1,
    "size": 1,
    "capacity_formula": None,
    "output_formula": None,
}

STUDIO: dict[str, Any] = {
    "name": "Radio studio",
    "ability": SPECIALEnum.CHARISMA,
    "base_cost": 600,
    "incremental_cost": 150,
    "t2_upgrade_cost": 1500,
    "t3_upgrade_cost": 4500,
    "capacity_formula": None,
    "output_formula": None,
}


async def _create_existing_room(
    session: AsyncSession,
    vault_id: UUID,
    *,
    name: str = "Power Generator",
    coordinate_x: int,
    coordinate_y: int = 1,
    size: int = 3,
    size_max: int = 9,
    tier: int = 1,
    capacity_formula: str | None = "10*S",
    output_formula: str | None = "5*S",
    image_url: str | None = None,
) -> Room:
    obj_in = _payload(
        vault_id,
        name=name,
        coordinate_x=coordinate_x,
        coordinate_y=coordinate_y,
        size=size,
        size_max=size_max,
        tier=tier,
        capacity_formula=capacity_formula,
        output_formula=output_formula,
        image_url=image_url,
    )
    return await crud.room.create(session, obj_in=obj_in)


async def _elevator(session: AsyncSession, vault: Vault | UUID, coordinate_y: int, *, coordinate_x: int = 6) -> Room:
    vault_id = vault if isinstance(vault, UUID) else vault.id
    obj_in = _payload(vault_id, **{**ELEVATOR, "coordinate_x": coordinate_x, "coordinate_y": coordinate_y})
    return await crud.room.create(session, obj_in=obj_in)


def _radio(vault: Vault, *, coordinate_x: int, coordinate_y: int = 0, size: int = 3, tier: int = 1) -> RoomCreate:
    return _pc(
        vault, **{**STUDIO, "coordinate_x": coordinate_x, "coordinate_y": coordinate_y, "size": size, "tier": tier}
    )


def _response(vault: Vault, *, coordinate_x: int, coordinate_y: int = 0, size: int = 3) -> RoomCreate:
    return _pc(
        vault,
        name="Response Station",
        category=RoomTypeEnum.RESPONSE,
        ability=SPECIALEnum.ENDURANCE,
        base_cost=600,
        incremental_cost=None,
        t2_upgrade_cost=None,
        t3_upgrade_cost=None,
        size=size,
        coordinate_x=coordinate_x,
        coordinate_y=coordinate_y,
        capacity_formula=None,
        output_formula=None,
    )


# Names kept for app/tests/test_api/test_room.py, which builds its fixtures through them.
_create_elevator = _elevator


async def _create_radio_studio(
    session: AsyncSession, vault_id: UUID, *, coordinate_x: int = 1, coordinate_y: int = 0, size: int = 3, tier: int = 1
) -> Room:
    obj_in = _payload(
        vault_id, **{**STUDIO, "coordinate_x": coordinate_x, "coordinate_y": coordinate_y, "size": size, "tier": tier}
    )
    return await crud.room.create(session, obj_in=obj_in)


async def _room(session: AsyncSession, vault: Vault, **overrides: Any) -> Room:
    return await crud.room.create(session, obj_in=_pc(vault, **overrides))


async def _station(session: AsyncSession, vault: Vault, **kw: Any) -> Room:
    return await crud.room.create(session, obj_in=_response(vault, **kw))


async def _studio(session: AsyncSession, vault: Vault, **kw: Any) -> Room:
    return await crud.room.create(session, obj_in=_radio(vault, **kw))


async def _names(session: AsyncSession, vault: Vault) -> list[str]:
    return await crud.room.get_names_by_vault(session, vault.id)


async def _caps(session: AsyncSession, vault: Vault) -> int:
    """Bottle caps as persisted, re-read after a call that may have rolled back."""
    await session.refresh(vault)
    return vault.bottle_caps


async def _dweller(session: AsyncSession, vault: Vault, room: Room, **stats: Any) -> Any:
    dweller = await crud.dweller.create(
        session, obj_in=DwellerCreate(vault_id=vault.id, **create_rush_dweller_payload(**stats))
    )
    dweller.room_id = room.id
    session.add(dweller)
    await session.commit()
    await session.refresh(dweller)
    return dweller


async def _build(session: AsyncSession, payload: RoomCreate):
    with patch(RECALC, new_callable=AsyncMock):
        return await room_service._build(db_session=session, obj_in=payload)


async def _upgrade(session: AsyncSession, room_id: UUID):
    with patch(RECALC, new_callable=AsyncMock):
        return await room_service._upgrade(session, room_id)


@pytest.fixture
async def rich_vault(vault: Vault, async_session: AsyncSession) -> Vault:
    vault.bottle_caps = 1_000_000
    async_session.add(vault)
    await async_session.commit()
    await async_session.refresh(vault)
    return vault


@pytest.fixture(autouse=True)
def _stub_room_template():
    """Use the formulas provided in test RoomCreate payloads, not the static store."""
    with patch("app.services.room_service.game_data_store.get_room", return_value=None):
        yield


# _build merge scenarios


async def test_build_merges_adjacent_room_on_right(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    existing = await _room(async_session, rich_vault, coordinate_x=0, tier=2)
    result, created = await _build(async_session, _pc(rich_vault, coordinate_x=3, tier=2))
    assert (result.id, created, result.coordinate_x, result.size) == (existing.id, False, 0, 6)
    assert (result.capacity, result.output) == (60, 30)


async def test_build_merges_adjacent_room_on_left(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    existing = await _room(async_session, rich_vault, coordinate_x=3, tier=2)
    result, created = await _build(async_session, _pc(rich_vault, coordinate_x=0, tier=2))
    assert (result.id != existing.id, created, result.coordinate_x, result.size) == (True, True, 0, 6)
    remaining = await crud.room.get_all_by_vault(async_session, rich_vault.id)
    assert existing.id not in {room.id for room in remaining}


async def test_build_three_way_merge_to_size_max(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    left = await _room(async_session, rich_vault, coordinate_x=0)
    right = await _room(async_session, rich_vault, coordinate_x=6)
    result, created = await _build(async_session, _pc(rich_vault, coordinate_x=3))
    assert (result.id, created, result.size, result.coordinate_x) == (left.id, False, 9, 0)
    remaining_ids = {room.id for room in await crud.room.get_all_by_vault(async_session, rich_vault.id)}
    assert left.id in remaining_ids
    assert right.id not in remaining_ids


@pytest.mark.parametrize(
    ("existing_kw", "new_kw", "expected_name"),
    [
        ({"tier": 1}, {"tier": 2}, "Power Generator"),
        ({}, {"name": "Diner"}, "Diner"),
        ({"size_max": 3}, {"size_max": 3}, "Power Generator"),
    ],
)
async def test_build_no_merge(async_session, rich_vault, existing_kw, new_kw, expected_name):
    await _elevator(async_session, rich_vault, 1)
    existing = await _room(async_session, rich_vault, **existing_kw)
    result, created = await _build(async_session, _pc(rich_vault, coordinate_x=3, **new_kw))
    assert (created, result.id != existing.id, result.size, result.name) == (True, True, 3, expected_name)


async def test_build_same_coordinate_same_name_expands(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    existing = await _room(async_session, rich_vault, coordinate_x=0)
    result, created = await _build(async_session, _pc(rich_vault, coordinate_x=0))
    assert (result.id, created, result.size) == (existing.id, False, 6)


async def test_build_merge_reassigns_dwellers(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    existing = await _room(async_session, rich_vault, coordinate_x=0)
    await _dweller(async_session, rich_vault, existing)
    result, _created = await _build(async_session, _pc(rich_vault, coordinate_x=3))
    dwellers = await crud.dweller.get_by_room(async_session, result.id)
    assert len(dwellers) == 1
    assert dwellers[0].room_id == result.id


@pytest.mark.parametrize(("size", "expected_price"), [(3, 125), (6, 150)])
async def test_build_merge_charges_price(async_session, rich_vault, size, expected_price):
    await _elevator(async_session, rich_vault, 1, coordinate_x=9)
    await _room(async_session, rich_vault, coordinate_x=0, size=size)
    caps_before = rich_vault.bottle_caps
    result, _created = await room_service._build(db_session=async_session, obj_in=_pc(rich_vault, coordinate_x=size))
    assert await _caps(async_session, rich_vault) == caps_before - expected_price
    assert result.size == size + 3


async def test_build_merge_recomputes_image_url(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    existing = await _room(async_session, rich_vault, coordinate_x=0)
    existing.image_url = "/static/old.png"
    async_session.add(existing)
    await async_session.commit()
    result, _created = await _build(async_session, _pc(rich_vault, coordinate_x=3))
    assert result.image_url != "/static/old.png"


# Backfill merge-rooms


@pytest.mark.parametrize(("xs", "expected"), [((0, 3), 1), ((0, 3, 6), 2)])
async def test_backfill_dry_run_reports_without_writing(async_session, rich_vault, xs, expected):
    await _elevator(async_session, rich_vault, 1, coordinate_x=9)
    for coordinate_x in xs:
        await _room(async_session, rich_vault, coordinate_x=coordinate_x)
    rooms_before = len(await crud.room.get_all_by_vault(async_session, rich_vault.id))
    dry = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=True)
    assert dry["merged"] == expected
    assert len(await crud.room.get_all_by_vault(async_session, rich_vault.id)) == rooms_before
    applied = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)
    assert applied["merged"] == expected


async def test_backfill_merge_rooms_apply_merges(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    left = await _room(async_session, rich_vault, coordinate_x=0)
    right = await _room(async_session, rich_vault, coordinate_x=3)
    left_dweller = await _dweller(async_session, rich_vault, left)
    right_dweller = await _dweller(async_session, rich_vault, right)
    summary = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)
    assert summary["merged"] == 1
    survivor = await crud.room.get(async_session, left.id)
    assert survivor.size == 6
    await async_session.refresh(left_dweller)
    await async_session.refresh(right_dweller)
    assert (left_dweller.room_id, right_dweller.room_id) == (survivor.id, survivor.id)
    with pytest.raises(ResourceNotFoundException):
        await crud.room.get(async_session, right.id)


async def test_backfill_merge_rooms_idempotent(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    await _room(async_session, rich_vault, coordinate_x=0)
    await _room(async_session, rich_vault, coordinate_x=3)
    first = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)
    second = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)
    assert (first["merged"], second["merged"]) == (1, 0)


async def test_backfill_skips_unplaced_rooms_without_sort_crash(async_session, rich_vault):
    # Unplaced (NULL-coordinate) rooms must not crash the backfill sort.
    await _elevator(async_session, rich_vault, 1)
    await _room(async_session, rich_vault, coordinate_x=0)
    await _room(async_session, rich_vault, coordinate_x=3)
    await _room(async_session, rich_vault, name="Storage", coordinate_x=None, coordinate_y=None)
    summary = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=True)
    assert summary["merged"] == 1


async def _training(session: AsyncSession, vault: Vault, dweller: Any, room: Room, **kw: Any) -> Training:
    training = Training(
        vault_id=vault.id,
        dweller_id=dweller.id,
        room_id=room.id,
        stat_being_trained=SPECIALEnum.STRENGTH,
        current_stat_value=5,
        target_stat_value=6,
        started_at=utcnow(),
        estimated_completion_at=utcnow(),
        **kw,
    )
    session.add(training)
    await session.commit()
    return training


async def test_build_merge_reassigns_training_and_dwellers(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    absorbed = await _room(async_session, rich_vault, coordinate_x=3)
    dweller = await _dweller(async_session, rich_vault, absorbed)
    training = await _training(async_session, rich_vault, dweller, absorbed)
    survivor, _ = await _build(async_session, _pc(rich_vault, coordinate_x=0, tier=1))
    await async_session.refresh(training)
    await async_session.refresh(dweller)
    assert survivor.size == 6
    assert (training.room_id, dweller.room_id) == (survivor.id, survivor.id)


# _upgrade merge scenarios


@pytest.mark.parametrize(("neighbor_tier", "merges"), [(2, True), (3, False)])
async def test_upgrade_merge_respects_tier(async_session, rich_vault, neighbor_tier, merges):
    await _elevator(async_session, rich_vault, 1)
    neighbor = await _room(async_session, rich_vault, coordinate_x=0, tier=neighbor_tier)
    upgraded = await _room(async_session, rich_vault, coordinate_x=3, tier=1)
    dweller = await _dweller(async_session, rich_vault, upgraded)
    result = await _upgrade(async_session, upgraded.id)
    if merges:
        assert (result.id, result.tier, result.size) == (neighbor.id, 2, 6)
        with pytest.raises(ResourceNotFoundException):
            await crud.room.get(async_session, upgraded.id)
        await async_session.refresh(dweller)
        assert dweller.room_id == neighbor.id
    else:
        assert (result.id, result.tier, result.size) == (upgraded.id, 2, 3)


# Response Station — unique room growth via an adjacent segment (issue #997)


async def test_adjacent_station_segment_merges_into_one_row(async_session, rich_vault):
    station = await _station(async_session, rich_vault, coordinate_x=1)
    assert calculate_room_capacity(station.size) == 2
    starting_caps = rich_vault.bottle_caps
    grown_to_six, created = await _build(async_session, _response(rich_vault, coordinate_x=4))
    assert (grown_to_six.id, created, grown_to_six.size) == (station.id, False, 6)
    assert calculate_room_capacity(grown_to_six.size) == 4
    grown_to_nine, created = await _build(async_session, _response(rich_vault, coordinate_x=7))
    assert (grown_to_nine.id, created, grown_to_nine.size) == (station.id, False, 9)
    assert calculate_room_capacity(grown_to_nine.size) == 6
    assert await _caps(async_session, rich_vault) == starting_caps - 1200
    assert (await _names(async_session, rich_vault)).count("Response Station") == 1


async def test_adjacent_station_segment_preserves_dwellers(async_session, rich_vault):
    station = await _station(async_session, rich_vault, coordinate_x=1)
    dweller = await _dweller(async_session, rich_vault, station)
    grown, _created = await _build(async_session, _response(rich_vault, coordinate_x=4))
    assert grown.id == station.id
    await async_session.refresh(dweller)
    assert dweller.room_id == station.id
    assert (await _names(async_session, rich_vault)).count("Response Station") == 1


async def test_disconnected_second_station_rejected_without_charge(async_session, rich_vault):
    await _station(async_session, rich_vault, coordinate_x=1)
    await _elevator(async_session, rich_vault, 1, coordinate_x=0)
    starting_caps = rich_vault.bottle_caps
    with pytest.raises(UniqueRoomViolationException):
        await room_service._build(
            db_session=async_session, obj_in=_response(rich_vault, coordinate_x=1, coordinate_y=1)
        )
    assert await _caps(async_session, rich_vault) == starting_caps
    assert (await _names(async_session, rich_vault)).count("Response Station") == 1


async def test_adjacent_station_segment_at_size_max_rejected_without_charge(async_session, rich_vault):
    station = await _station(async_session, rich_vault, coordinate_x=1, size=9)
    starting_caps = rich_vault.bottle_caps
    with pytest.raises(UniqueRoomViolationException):
        await room_service._build(db_session=async_session, obj_in=_response(rich_vault, coordinate_x=10))
    assert await _caps(async_session, rich_vault) == starting_caps
    await async_session.refresh(station)
    assert station.size == 9
    assert (await _names(async_session, rich_vault)).count("Response Station") == 1


# Radio studio — one per vault, still growable through adjacent segments


async def test_adjacent_radio_segment_merges_into_one_studio(async_session, rich_vault):
    studio = await _studio(async_session, rich_vault, coordinate_x=1)
    starting_caps = rich_vault.bottle_caps
    grown_to_six, created = await room_service._build(
        db_session=async_session, obj_in=_radio(rich_vault, coordinate_x=4)
    )
    assert (grown_to_six.id, created, grown_to_six.size) == (studio.id, False, 6)
    assert await _caps(async_session, rich_vault) == starting_caps - 750
    grown_to_nine, created = await room_service._build(
        db_session=async_session, obj_in=_radio(rich_vault, coordinate_x=7)
    )
    assert (grown_to_nine.id, created, grown_to_nine.size) == (studio.id, False, 9)
    assert await _caps(async_session, rich_vault) == starting_caps - 1650
    assert (await _names(async_session, rich_vault)).count("Radio studio") == 1


async def test_disconnected_second_radio_studio_rejected_without_charge(async_session, rich_vault):
    await _studio(async_session, rich_vault, coordinate_x=1)
    await _elevator(async_session, rich_vault, 1, coordinate_x=0)
    starting_caps = rich_vault.bottle_caps
    with pytest.raises(UniqueRoomViolationException) as excinfo:
        await room_service._build(db_session=async_session, obj_in=_radio(rich_vault, coordinate_x=1, coordinate_y=1))
    detail = str(excinfo.value)
    assert "Radio studio" in detail
    assert "adjacent" in detail
    assert await _caps(async_session, rich_vault) == starting_caps
    assert (await _names(async_session, rich_vault)).count("Radio studio") == 1


async def _tier_case(session, vault, *, upgrade, neighbor):
    room = await _studio(session, vault, coordinate_x=1, tier=1 if upgrade else 2)
    if upgrade:
        await room_service.upgrade_room(session, room.id)
    await _studio(session, vault, **neighbor)
    return room


@pytest.mark.parametrize(
    ("upgrade", "neighbor", "caps_spent"),
    [
        (True, {"coordinate_x": 1, "coordinate_y": 1}, None),
        (True, {"coordinate_x": 7, "size": 9, "tier": 3}, 2700),
        (False, {"coordinate_x": 7}, 2400),
    ],
)
async def test_adjacent_tier_resolution_grows_the_touching_studio(
    async_session, rich_vault, upgrade, neighbor, caps_spent
):
    expected = await _tier_case(async_session, rich_vault, upgrade=upgrade, neighbor=neighbor)
    starting_caps = rich_vault.bottle_caps
    grown, _ = await room_service._build(db_session=async_session, obj_in=_radio(rich_vault, coordinate_x=4))
    assert (grown.id, grown.tier, grown.size) == (expected.id, 2, 6)
    if caps_spent:
        await async_session.refresh(rich_vault)
        assert rich_vault.bottle_caps == starting_caps - caps_spent


async def test_split_radio_studio_rejected_by_remodel_service(async_session, rich_vault):
    studio = await _studio(async_session, rich_vault, coordinate_x=1, size=6)
    with pytest.raises(UniqueRoomViolationException, match="cannot be split"):
        await remodel_room(async_session, studio.id)
    await async_session.refresh(studio)
    assert studio.size == 6
    assert (await _names(async_session, rich_vault)).count("Radio studio") == 1


async def test_explicit_merge_of_legacy_radio_studios_still_succeeds(async_session, rich_vault):
    # Legacy duplicate studios can still merge; only building and splitting are blocked.
    left = await _studio(async_session, rich_vault, coordinate_x=1)
    right = await _studio(async_session, rich_vault, coordinate_x=4)
    merged = (await remodel_room(async_session, left.id, right.id))[0]
    assert (merged.id, merged.size) == (left.id, 6)
    assert (await _names(async_session, rich_vault)).count("Radio studio") == 1


@asynccontextmanager
async def _placement_lock_held(*_args, **_kwargs):
    """Stand-in for hold_advisory_lock when another build owns the vault placement lock."""
    yield False


async def _lock_op(kind, session, vault, room_id):
    if kind == "build":
        await room_service._build(db_session=session, obj_in=_response(vault, coordinate_x=1))
    elif kind == "upgrade":
        await room_service._upgrade(session, room_id)
    elif kind == "backfill":
        await room_service.backfill_merge_rooms_for_vault(session, vault.id, dry_run=False)
    elif kind == "destroy":
        await room_service.destroy_room(session, room_id)
    else:
        await room_service.apply_room_style(session, room_id, "default")


@pytest.mark.parametrize("kind", ["build", "upgrade", "backfill", "destroy", "style"])
async def test_operation_refused_when_vault_placement_lock_is_held(async_session, rich_vault, kind):
    await _elevator(async_session, rich_vault, 1)
    left = await _room(async_session, rich_vault, coordinate_x=0)
    await _room(async_session, rich_vault, coordinate_x=3)
    starting_caps = rich_vault.bottle_caps
    with patch(LOCK, new=_placement_lock_held), pytest.raises(ResourceConflictException):
        await _lock_op(kind, async_session, rich_vault, left.id)
    assert await _caps(async_session, rich_vault) == starting_caps
    assert await crud.room.get(async_session, left.id)


async def test_backfill_dry_run_ignores_vault_placement_lock(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    await _room(async_session, rich_vault, coordinate_x=0)
    await _room(async_session, rich_vault, coordinate_x=3)
    with patch(LOCK, new=_placement_lock_held):
        summary = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=True)
    assert summary["merged"] == 1


async def test_boosted_seeded_station_grows_to_nine(async_session, rich_vault):
    # The seeded station at (13, 0) must have free adjacent cells at (16, 0) and (19, 0).
    game_data = await get_static_game_data()
    prepared = seeding.prepare_initial_rooms(game_data.rooms, rich_vault.id, is_boosted=True)
    await crud.vault.create_storage(db_session=async_session, vault_id=rich_vault.id)
    await seeding.create_initial_rooms(async_session, rich_vault, prepared)
    station = next(
        room
        for room in await crud.room.get_all_by_vault(async_session, rich_vault.id)
        if room.name == "Response Station"
    )
    assert station.size == 3
    assert calculate_room_capacity(station.size) == 2
    grown_to_six, _created = await _build(async_session, _response(rich_vault, coordinate_x=16, coordinate_y=0))
    assert (grown_to_six.id, grown_to_six.size, calculate_room_capacity(grown_to_six.size)) == (station.id, 6, 4)
    grown_to_nine, _created = await _build(async_session, _response(rich_vault, coordinate_x=19, coordinate_y=0))
    assert (grown_to_nine.id, grown_to_nine.size, calculate_room_capacity(grown_to_nine.size)) == (station.id, 9, 6)
    assert (await _names(async_session, rich_vault)).count("Response Station") == 1


@pytest.mark.parametrize(("inner_x", "outer_x", "size"), [(7, 10, 3), (3, 0, 3), (7, 16, 9)])
async def test_destroy_requires_outermost_room(async_session, rich_vault, inner_x, outer_x, size):
    await _elevator(async_session, rich_vault, 1)
    inner = await _room(async_session, rich_vault, coordinate_x=inner_x, size=size)
    outer = await _room(async_session, rich_vault, coordinate_x=outer_x)
    dweller = await _dweller(async_session, rich_vault, inner)
    caps = rich_vault.bottle_caps
    with pytest.raises(VaultOperationException, match="end of a row"):
        await room_service.destroy_room(async_session, inner.id)
    await async_session.refresh(rich_vault)
    await async_session.refresh(dweller)
    assert (rich_vault.bottle_caps, dweller.room_id) == (caps, inner.id)
    assert await crud.room.get(async_session, inner.id)
    await room_service.destroy_room(async_session, outer.id)
    await room_service.destroy_room(async_session, inner.id)


async def test_destroy_defers_refund_event_until_after_commit(async_session, rich_vault, monkeypatch):
    # RESOURCE_COLLECTED listeners lock the vault row in their own session, so emitting inside the
    # still-open destroy transaction deadlocks them against its uncommitted caps update.
    outer = await _room(async_session, rich_vault, coordinate_x=7)
    deposit_calls: list[dict[str, Any]] = []
    emitted: list[tuple[str, dict[str, Any]]] = []

    async def fake_deposit_caps(**kwargs: Any) -> int:
        deposit_calls.append(kwargs)
        return 17

    async def handler(event_type: str, vault_id: UUID, data: dict[str, Any]) -> None:
        emitted.append((event_type, data))

    monkeypatch.setattr(vault_service, "deposit_caps", fake_deposit_caps)
    event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler)
    try:
        await room_service.destroy_room(async_session, outer.id)
    finally:
        event_bus.unsubscribe(GameEvent.RESOURCE_COLLECTED, handler)
    assert deposit_calls
    assert deposit_calls[0]["emit_event"] is False
    assert emitted == [(GameEvent.RESOURCE_COLLECTED, {"resource_type": "caps", "amount": 17})]


async def test_destroy_lowest_elevator_on_empty_floor(async_session, rich_vault):
    rich_vault.bottle_caps = 1000
    async_session.add(rich_vault)
    await async_session.commit()
    above = await _elevator(async_session, rich_vault, 1)
    lowest = await _elevator(async_session, rich_vault, 2)
    above_id, lowest_id = above.id, lowest.id
    initial_caps = rich_vault.bottle_caps
    destroyed = await room_service.destroy_room(async_session, lowest_id)
    assert destroyed.id == lowest_id
    assert await async_session.get(Room, lowest_id) is None
    assert await crud.room.get(async_session, above_id)
    assert await _caps(async_session, rich_vault) == initial_caps + 50


@pytest.mark.parametrize("room_x", [3, 7])
async def test_destroy_lowest_elevator_with_attached_room_rejected(async_session, rich_vault, room_x):
    await _elevator(async_session, rich_vault, 1)
    lowest = await _elevator(async_session, rich_vault, 2)
    attached = await _room(async_session, rich_vault, coordinate_x=room_x, coordinate_y=2)
    vault_id, lowest_id, attached_id = rich_vault.id, lowest.id, attached.id
    initial_caps = rich_vault.bottle_caps
    with pytest.raises(VaultOperationException, match="only access to level 2"):
        await room_service.destroy_room(async_session, lowest_id)
    await async_session.rollback()
    assert await crud.room.get(async_session, lowest_id)
    assert await crud.room.get(async_session, attached_id)
    assert (await crud.vault.get(async_session, vault_id)).bottle_caps == initial_caps


@pytest.mark.parametrize(("size", "tier"), [(6, 1), (9, 2), (9, 3)])
async def test_split_merge_preserves_room_totals_and_dwellers(async_session, rich_vault, size, tier):
    await _elevator(async_session, rich_vault, 1)
    source = await _room(async_session, rich_vault, coordinate_x=7, size=size, tier=tier)
    source.capacity, source.output = 101, 37
    async_session.add(source)
    await async_session.commit()
    residents = [await _dweller(async_session, rich_vault, source) for _ in range(size // 3 * 2)]
    rich_vault.bottle_caps = 5_000
    async_session.add(rich_vault)
    await async_session.commit()
    caps, refund = rich_vault.bottle_caps, room_refund(source)
    pieces = await remodel_room(async_session, source.id)
    assert [r.coordinate_x for r in pieces] == list(range(7, 7 + size, 3))
    assert all(r.size == 3 and r.tier == tier for r in pieces)
    assert sum(r.capacity for r in pieces) == 101
    assert sum(r.output for r in pieces) == 37
    assert sum(room_refund(r) for r in pieces) == refund
    for piece in pieces:
        assert len(await crud.dweller.get_by_room(async_session, piece.id)) == 2
    merged = pieces[0]
    for piece in pieces[1:]:
        merged = (await remodel_room(async_session, merged.id, piece.id))[0]
    assert (merged.size, merged.capacity, merged.output, merged.tier) == (size, 101, 37, tier)
    assert room_refund(merged) == refund
    assert rich_vault.bottle_caps == caps
    for resident in residents:
        await async_session.refresh(resident)
        assert resident.room_id == merged.id
    # Round trips retain the exact rounded refund even after repeated splitting.
    pieces = await remodel_room(async_session, merged.id)
    for piece in reversed(pieces):
        await room_service.destroy_room(async_session, piece.id)
    assert await _caps(async_session, rich_vault) == caps + refund


@pytest.mark.parametrize(
    "change", [{"tier": 2}, {"name": "Diner"}, {"coordinate_x": 13}, {"coordinate_y": 2}, {"size": 9}]
)
async def test_manual_merge_rejects_incompatible_neighbors(async_session, rich_vault, change):
    left = await _room(async_session, rich_vault, coordinate_x=7)
    right = await _room(async_session, rich_vault, coordinate_x=10)
    await crud.room.update(async_session, right.id, change)
    with pytest.raises(VaultOperationException):
        await remodel_room(async_session, left.id, right.id)
    assert len(await crud.room.get_all_by_vault(async_session, rich_vault.id)) == 2


async def test_split_requires_multiple_base_segments_and_free_placement_lock(async_session, rich_vault):
    source = await _room(async_session, rich_vault, coordinate_x=7)
    with pytest.raises(VaultOperationException, match="one base segment"):
        await remodel_room(async_session, source.id)
    with patch(LOCK, new=_placement_lock_held), pytest.raises(ResourceConflictException):
        await remodel_room(async_session, source.id)


async def test_remodel_training_and_incident_references_follow_survivor(async_session, rich_vault):
    source = await _room(async_session, rich_vault, coordinate_x=7, size=6)
    dwellers = [await _dweller(async_session, rich_vault, source) for _ in range(4)]
    trainings = [await _training(async_session, rich_vault, d, source, progress=0.45) for d in dwellers]
    pieces = await remodel_room(async_session, source.id)
    for training, dweller in zip(trainings, dwellers, strict=True):
        await async_session.refresh(training)
        await async_session.refresh(dweller)
        assert (training.room_id, training.progress) == (dweller.room_id, 0.45)
    incident = Incident(
        vault_id=rich_vault.id,
        room_id=pieces[1].id,
        type=IncidentType.FIRE,
        difficulty=1,
        rooms_affected=[str(pieces[1].id)],
    )
    async_session.add(incident)
    await async_session.commit()
    with pytest.raises(VaultOperationException, match="Resolve the incident"):
        await remodel_room(async_session, pieces[0].id, pieces[1].id)
    incident.status = IncidentStatus.RESOLVED
    async_session.add(incident)
    await async_session.commit()
    merged = (await remodel_room(async_session, pieces[1].id, pieces[0].id))[0]
    await async_session.refresh(incident)
    assert incident.room_id == merged.id
    assert incident.rooms_affected == [str(merged.id)]
    for training in trainings:
        await async_session.refresh(training)
        assert training.room_id == merged.id


async def test_split_preserves_dispatched_return_postings(async_session, rich_vault):
    source = await _room(async_session, rich_vault, coordinate_x=7, size=6)
    residents = [await _dweller(async_session, rich_vault, source) for _ in range(4)]
    team = Team(vault_id=rich_vault.id, name="Return crew", exploration_id=source.id)
    async_session.add(team)
    await async_session.flush()
    members = [TeamMember(team_id=team.id, dweller_id=d.id, origin_room_id=source.id) for d in residents]
    for d in residents:
        d.room_id = None
        async_session.add(d)
    async_session.add_all(members)
    await async_session.commit()
    pieces = await remodel_room(async_session, source.id)
    for member in members:
        await async_session.refresh(member)
    assert sorted(sum(m.origin_room_id == p.id for m in members) for p in pieces) == [2, 2]
    for d in residents:
        await async_session.refresh(d)
        assert d.room_id is None


async def test_split_failure_rolls_back_the_entire_layout(async_session, rich_vault):
    source = await _room(async_session, rich_vault, coordinate_x=7, size=6)
    vault_id, source_id = rich_vault.id, source.id
    connection = await async_session.connection()

    def fail_insert(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("INSERT INTO room "):
            raise OperationalError(statement, {}, RuntimeError("injected insert failure"))

    event.listen(connection.sync_connection, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises(OperationalError, match="injected insert failure"):
            await remodel_room(async_session, source_id)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", fail_insert)
        await async_session.rollback()
    rooms = await crud.room.get_all_by_vault(async_session, vault_id)
    assert [(r.id, r.coordinate_x, r.size, r.refund_caps) for r in rooms] == [(source_id, 7, 6, None)]


async def test_remodeled_refunds_survive_upgrades_and_automatic_merging(async_session, rich_vault):
    source = await _room(async_session, rich_vault, coordinate_x=7, size=9)
    refund = room_refund(source)
    pieces = await remodel_room(async_session, source.id)
    for piece in pieces:
        await room_service.upgrade_room(async_session, piece.id)
    remaining = await crud.room.get_all_by_vault(async_session, rich_vault.id)
    assert len(remaining) == 1
    assert (remaining[0].size, remaining[0].tier) == (9, 2)
    assert room_refund(remaining[0]) == refund + 750


async def test_buildable_rooms_are_sorted_by_population_requirement():
    game_data = await get_static_game_data()
    rooms = game_data.get_buildable_rooms(set())
    keys = [(room.population_required is not None, room.population_required or 0) for room in rooms]
    assert keys == sorted(keys)
    arena = next(room for room in rooms if room.name == "Arena")
    assert arena.population_required == 55
    assert arena.is_unique is True
    assert arena.base_cost == 3000
    assert (arena.t2_upgrade_cost, arena.t3_upgrade_cost) == (12000, 36000)


async def test_unaffordable_build_does_not_expand_adjacent_room(async_session, vault):
    vault.bottle_caps = 0
    async_session.add(vault)
    await async_session.commit()
    await _elevator(async_session, vault, 1)
    existing = await _room(async_session, vault, coordinate_x=0)
    room_id, initial_size = existing.id, existing.size
    with pytest.raises(InsufficientResourcesException):
        await room_service._build(db_session=async_session, obj_in=_pc(vault, coordinate_x=3))
    await async_session.rollback()
    persisted = await crud.room.get(async_session, room_id)
    assert persisted.size == initial_size


async def _failing_op(session, vault, kind, room_id):
    if kind == "build":
        await room_service._build(db_session=session, obj_in=_pc(vault, coordinate_x=3))
    elif kind == "upgrade":
        await room_service._upgrade(session, room_id)
    else:
        await room_service.destroy_room(session, room_id)


@pytest.mark.parametrize(
    ("kind", "prefix", "message"),
    [
        ("build", "INSERT INTO ROOM", "injected room insert failure"),
        ("upgrade", "UPDATE ROOM", "injected room update failure"),
        ("destroy", "UPDATE VAULT", "injected refund failure"),
        ("destroy_elevator", "UPDATE VAULT", "injected refund failure"),
    ],
)
async def test_write_failure_preserves_state(async_session, db_connection, rich_vault, kind, prefix, message):
    await _elevator(async_session, rich_vault, 1)
    room = (
        None
        if kind == "build"
        else await (
            _elevator(async_session, rich_vault, 2)
            if kind == "destroy_elevator"
            else _room(async_session, rich_vault, coordinate_x=0)
        )
    )
    vault_id, room_id = rich_vault.id, room and room.id
    initial_caps = rich_vault.bottle_caps

    def fail(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(prefix):
            raise RuntimeError(message)

    connection = db_connection.sync_connection
    event.listen(connection, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match=message):
            await _failing_op(async_session, rich_vault, kind, room_id)
    finally:
        event.remove(connection, "before_cursor_execute", fail)

    await async_session.rollback()
    persisted_vault = await crud.vault.get(async_session, vault_id)
    assert persisted_vault.bottle_caps == initial_caps
    if room_id is not None:
        persisted_room = await crud.room.get(async_session, room_id)
        assert persisted_room.id == room_id
        if kind == "upgrade":
            assert persisted_room.tier == 1


async def test_build_commits_once_on_create_and_merge_paths(async_session, rich_vault):
    await _elevator(async_session, rich_vault, 1)
    commits = counting_commit(async_session)
    await room_service._build(db_session=async_session, obj_in=_pc(rich_vault, coordinate_x=3))
    assert len(commits) == 1
    await room_service._build(db_session=async_session, obj_in=_pc(rich_vault, coordinate_x=0))
    assert len(commits) == 2
