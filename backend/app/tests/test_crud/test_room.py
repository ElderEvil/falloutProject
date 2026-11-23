"""Tests for CRUDRoom persistence helpers and RoomService orchestration."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.core.game_config import GRID_X_MAX, GRID_X_MIN, GRID_Y_MAX, GRID_Y_MIN, game_config
from app.crud.room import CRUDRoom
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.room import RoomCreate
from app.services.room_service import RoomService
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceNotFoundException,
    UniqueRoomViolationException,
    VaultOperationException,
)
from app.utils.room_assets import get_room_image_url

_DEFAULTS = {
    "name": "Test Room",
    "category": RoomTypeEnum.PRODUCTION,
    "tier": 1,
    "size": 3,
    "size_max": 6,
    "coordinate_x": 2,
    "coordinate_y": 2,
    "base_cost": 100,
    "incremental_cost": 25,
    "t2_upgrade_cost": 500,
    "t3_upgrade_cost": 1500,
    "capacity": 10,
    "output": 50,
    "population_required": None,
    "ability": SPECIALEnum.STRENGTH,
}


async def test_formula_evaluation_returns_zero_on_bad_input(room_crud) -> None:
    assert room_crud.evaluate_capacity_formula("S / unknown_var", level=3, size=5) == 0
    assert room_crud.evaluate_output_formula("int('abc')", level=3, size=5) == 0


@pytest.fixture
def room_crud() -> CRUDRoom:
    return CRUDRoom(Room)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _make_room(**overrides) -> Room:
    return Room(**({"id": uuid4(), "vault_id": uuid4(), "size_min": 3, "image_url": None} | _DEFAULTS | overrides))


def _make_room_create(**overrides) -> RoomCreate:
    return RoomCreate(**({"vault_id": uuid4(), "size_min": 1} | _DEFAULTS | overrides))


async def _create_room(session: AsyncSession, vault_id, **overrides) -> Room:
    """Persist a real Room row so the CRUD queries under test run actual SQL."""
    return await crud.room.create(db_session=session, obj_in=_make_room_create(vault_id=vault_id, **overrides))


async def _funded(session: AsyncSession, vault: Vault, caps: int = 100_000) -> None:
    await crud.vault.update(db_session=session, id=vault.id, obj_in={"bottle_caps": caps})


async def test_vault_room_queries(room_crud, async_session: AsyncSession, vault: Vault) -> None:
    rooms = [
        await _create_room(async_session, vault.id, name=name, coordinate_x=x)
        for name, x in (("Diner", 1), ("Kitchen", 3), ("Living Room", 7), ("DINER", 9), ("Elevator", 11))
    ]
    result = await room_crud.get_multy_by_vault(db_session=async_session, vault_id=vault.id, skip=0, limit=10)
    assert {room.id for room in result} == {room.id for room in rooms}
    names = await room_crud.get_existing_room_names(db_session=async_session, vault_id=vault.id)
    assert names == {"diner", "kitchen", "living room", "elevator"}


async def test_build_price_unique_rooms_charge_base_cost(room_crud, async_session: AsyncSession, vault: Vault) -> None:
    # A unique room (zero/null incremental cost) is priced at its base cost, regardless of
    # how many same-category rooms already exist; is_unique defines the zero/null marker.
    for coordinate_x in (1, 3):
        await _create_room(async_session, vault.id, category=RoomTypeEnum.PRODUCTION, coordinate_x=coordinate_x)
    zero = _make_room_create(vault_id=vault.id, base_cost=100, incremental_cost=0)
    assert zero.is_unique is True
    assert await room_crud.get_room_build_price(db_session=async_session, room_in=zero) == 100
    null = _make_room_create(vault_id=vault.id, category=RoomTypeEnum.PRODUCTION, base_cost=300, incremental_cost=None)
    assert null.is_unique is True
    assert await room_crud.get_room_build_price(db_session=async_session, room_in=null) == 300


async def test_build_price_counts_only_same_room_type(
    room_crud, async_session: AsyncSession, vault: Vault, user_with_vault
) -> None:
    await _create_room(async_session, vault.id, name="Power Generator", size_min=3, coordinate_x=1)
    await _create_room(async_session, vault.id, name="Power Generator", size_min=3, tier=2, coordinate_x=4)
    await _create_room(async_session, vault.id, name="Diner", coordinate_x=7)
    await _create_room(async_session, vault.id, name="Living room", category=RoomTypeEnum.CAPACITY, coordinate_x=10)
    _, other_vault = user_with_vault
    await _create_room(async_session, other_vault.id, name="Power Generator", size_min=3)
    room_in = _make_room_create(vault_id=vault.id, name="Power Generator", base_cost=100, incremental_cost=25)
    assert await room_crud.get_room_build_price(db_session=async_session, room_in=room_in) == 150


@pytest.mark.parametrize(("size", "expected"), [(None, 125), (3, 125), (6, 150), (9, 175)])
async def test_build_price_counts_merged_segments(
    room_crud, async_session: AsyncSession, vault: Vault, size, expected
) -> None:
    await _create_room(async_session, vault.id, name="Power Generator", size_min=3, size=size, size_max=9)
    room_in = _make_room_create(vault_id=vault.id, name="Power Generator", base_cost=100, incremental_cost=25)
    assert await room_crud.get_room_build_price(db_session=async_session, room_in=room_in) == expected


async def test_check_is_unique_room_rejects_existing(room_crud, async_session: AsyncSession, vault: Vault) -> None:
    await _create_room(async_session, vault.id, name="Vault Door", incremental_cost=0, coordinate_x=1)
    room_in = _make_room_create(vault_id=vault.id, name="Vault Door", incremental_cost=0)  # is_unique=True
    with pytest.raises(UniqueRoomViolationException):
        await room_crud.check_is_unique_room(db_session=async_session, obj_in=room_in)


@pytest.mark.parametrize(
    ("neighbor", "query_x", "matched"),
    [
        ((5, "Diner", 2), 2, True),
        ((0, "Diner", 2), 3, True),
        ((5, "Kitchen", 2), 2, False),
        ((5, "Diner", 3), 2, False),
    ],
    ids=["right-neighbor", "left-neighbor", "different-name", "different-row"],
)
async def test_adjacency_filters(room_crud, async_session: AsyncSession, vault: Vault, neighbor, query_x, matched):
    x, name, y = neighbor
    created = await _create_room(async_session, vault.id, name=name, tier=1, size=3, coordinate_x=x, coordinate_y=y)
    result = await room_crud.get_adjacent_mergeable_rooms(
        db_session=async_session, vault_id=vault.id, name="Diner", tier=1, coordinate_x=query_x, coordinate_y=2, size=3
    )
    assert [room.id for room in result] == ([created.id] if matched else [])


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        pytest.param({"size_min": 0, "size_max": 6}, "Invalid room size", id="size-min-below-1"),
        pytest.param({"size_min": None, "size_max": 6}, "Invalid room size", id="size-min-none"),
        pytest.param({"size_min": 5, "size_max": 3}, "Invalid room size", id="size-min-exceeds-max"),
        pytest.param({"size_min": 3, "size_max": None}, "Invalid room size", id="size-max-none"),
        pytest.param(
            {"coordinate_x": None, "coordinate_y": None}, "Room coordinates must be specified", id="coordinates-none"
        ),
        pytest.param({"coordinate_x": GRID_X_MIN - 1, "coordinate_y": 2}, "Invalid X coordinate", id="x-below-min"),
        pytest.param({"coordinate_x": GRID_X_MAX + 1, "coordinate_y": 2}, "Invalid X coordinate", id="x-above-max"),
        pytest.param({"coordinate_x": GRID_X_MAX, "size_min": 3}, "Room exceeds grid width", id="exceeds-grid-width"),
        pytest.param({"coordinate_x": 2, "coordinate_y": GRID_Y_MIN - 1}, "Invalid Y coordinate", id="y-below-min"),
        pytest.param({"coordinate_x": 2, "coordinate_y": GRID_Y_MAX + 1}, "Invalid Y coordinate", id="y-above-max"),
    ],
)
async def test_build_rejects_invalid_input(
    async_session: AsyncSession, vault: Vault, overrides: dict, message: str
) -> None:
    base = _make_room_create(vault_id=vault.id)
    room_in = RoomCreate.model_construct(**{**base.model_dump(exclude=set(overrides)), **overrides})
    with pytest.raises(ValueError, match=message):
        await RoomService()._build(db_session=async_session, obj_in=room_in)


async def test_build_rejects_second_vault_door(async_session: AsyncSession, vault: Vault) -> None:
    door = {"name": "Vault Door", "incremental_cost": 0, "size": 1, "size_min": 1, "coordinate_y": 0}
    await _create_room(async_session, vault.id, **door, coordinate_x=0)
    room_in = _make_room_create(vault_id=vault.id, **door, coordinate_x=1)
    with pytest.raises(UniqueRoomViolationException):
        await RoomService()._build(db_session=async_session, obj_in=room_in)


async def test_build_rejects_when_not_enough_dwellers(async_session: AsyncSession, vault: Vault) -> None:
    await _create_room(async_session, vault.id, name="Elevator", coordinate_x=5, coordinate_y=2, size=1, size_min=1)
    room_in = _make_room_create(vault_id=vault.id, population_required=20)
    with pytest.raises(InsufficientResourcesException):
        await RoomService()._build(db_session=async_session, obj_in=room_in)


async def test_build_merges_adjacent_same_name_room(async_session: AsyncSession, vault: Vault) -> None:
    await _funded(async_session, vault)
    await _create_room(async_session, vault.id, name="Elevator", coordinate_x=6, coordinate_y=2, size=1, size_min=1)
    survivor = await _create_room(
        async_session, vault.id, name="Diner", tier=1, size=3, size_min=3, coordinate_x=0, coordinate_y=2
    )
    room_in = _make_room_create(vault_id=vault.id, name="Diner", size=3, size_min=3, coordinate_x=3, coordinate_y=2)
    result, created = await RoomService()._build(db_session=async_session, obj_in=room_in)
    assert created is False
    assert result.id == survivor.id
    assert result.size == 6


async def test_unique_room_charges_base_price_and_rejects_second(async_session: AsyncSession, vault: Vault) -> None:
    # A unique room charges only its base price; a disconnected second room of the same
    # name is rejected before any caps are charged.
    await _funded(async_session, vault, caps=10_000)
    await _create_room(
        async_session,
        vault.id,
        name="Vault Door",
        incremental_cost=0,
        size=1,
        size_min=1,
        coordinate_x=0,
        coordinate_y=0,
    )
    unique = {
        "vault_id": vault.id,
        "name": "Response Station",
        "category": RoomTypeEnum.PRODUCTION,
        "base_cost": 500,
        "incremental_cost": 0,
        "size": 1,
        "size_min": 1,
        "coordinate_x": 1,
        "coordinate_y": 0,
    }
    room, created = await RoomService()._build(db_session=async_session, obj_in=_make_room_create(**unique))
    assert created is True
    assert room.name == "Response Station"
    assert vault.bottle_caps == 9_500
    # A neighbour makes the second cell buildable, but it is not adjacent to the first.
    await _create_room(async_session, vault.id, name="Diner", size=1, size_min=1, coordinate_x=4, coordinate_y=0)
    second = _make_room_create(**{**unique, "coordinate_x": 3})
    with pytest.raises(UniqueRoomViolationException):
        await RoomService()._build(db_session=async_session, obj_in=second)
    assert vault.bottle_caps == 9_500


async def test_build_allows_non_elevator_with_elevator_on_level(async_session: AsyncSession, vault: Vault) -> None:
    # Elevators gate level building: non-elevator rooms need an elevator on their level.
    await _funded(async_session, vault)
    await _create_room(async_session, vault.id, name="Elevator", coordinate_x=5, coordinate_y=5, size=1, size_min=1)
    room_in = _make_room_create(vault_id=vault.id, name="Diner", coordinate_x=2, coordinate_y=5)
    result, created = await RoomService()._build(db_session=async_session, obj_in=room_in)
    assert result.name == "Diner"
    assert result.coordinate_y == 5
    assert created is True


async def test_destroy_room_not_found(async_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundException):
        await RoomService().destroy_room(db_session=async_session, room_id=uuid4())


@pytest.mark.parametrize(
    ("overrides", "refund"),
    [
        (
            {
                "base_cost": 200,
                "incremental_cost": 50,
                "tier": 3,
                "t2_upgrade_cost": 500,
                "t3_upgrade_cost": 1500,
                "size": 3,
            },
            1125,
        ),
        (
            {
                "base_cost": 200,
                "incremental_cost": 50,
                "tier": 1,
                "t2_upgrade_cost": None,
                "t3_upgrade_cost": None,
                "size": 9,
            },
            375,
        ),
        (
            {
                "base_cost": 200,
                "incremental_cost": 50,
                "tier": 2,
                "t2_upgrade_cost": 500,
                "t3_upgrade_cost": 1500,
                "size": 9,
            },
            1125,
        ),
    ],
    ids=["upgrade-costs", "merged-segments", "merged-segment-upgrade-costs"],
)
async def test_destroy_refund(async_session: AsyncSession, vault: Vault, overrides: dict, refund: int) -> None:
    await _funded(async_session, vault)
    room = await _create_room(async_session, vault.id, category=RoomTypeEnum.CAPACITY, size_min=3, **overrides)
    with patch.object(game_config.resource, "destroy_room_refund_rate", 0.5):
        await RoomService().destroy_room(db_session=async_session, room_id=room.id)
    assert vault.bottle_caps == 100_000 + refund


async def test_destroy_rejects_different_case_vault_door(async_session: AsyncSession, vault: Vault) -> None:
    vault_door = await _create_room(
        async_session, vault.id, name="VAULT DOOR", incremental_cost=0, coordinate_x=0, coordinate_y=0
    )
    with pytest.raises(VaultOperationException, match="Cannot destroy the vault door"):
        await RoomService().destroy_room(db_session=async_session, room_id=vault_door.id)


async def test_upgrade_rejects_already_at_max_tier(async_session: AsyncSession, vault: Vault) -> None:
    room = await _create_room(
        async_session, vault.id, name="Diner", tier=3, t2_upgrade_cost=500, t3_upgrade_cost=1500, coordinate_x=1
    )
    with pytest.raises(VaultOperationException, match="already at maximum tier"):
        await RoomService().upgrade_room(db_session=async_session, room_id=room.id)


async def test_upgrade_rejects_missing_upgrade_cost(mock_session) -> None:
    # t3_upgrade_cost=0 is falsy (but not None), so max_tier=3 but no valid cost for tier 2.
    room = _make_room(tier=2, t2_upgrade_cost=500, t3_upgrade_cost=0)
    with (
        patch("app.crud.room.room.get", new_callable=AsyncMock, return_value=room),
        pytest.raises(VaultOperationException, match="No upgrade cost defined"),
    ):
        await RoomService().upgrade_room(db_session=mock_session, room_id=room.id)


@pytest.mark.parametrize(
    ("overrides", "expected_tier", "expected_cost"),
    [
        ({"capacity": 20, "output": 100, "size": 3, "size_min": 3, "tier": 2}, 3, 1500),
        ({"capacity": 10, "output": None, "size": 3, "size_min": 3, "t3_upgrade_cost": None}, 2, 500),
    ],
    ids=["tier2-to-tier3", "tier1-to-tier2"],
)
async def test_upgrade_charges_next_tier(
    async_session: AsyncSession, vault: Vault, overrides: dict, expected_tier: int, expected_cost: int
) -> None:
    await _funded(async_session, vault)
    base = {"category": RoomTypeEnum.CAPACITY, "t2_upgrade_cost": 500, "t3_upgrade_cost": 1500}
    room = await _create_room(async_session, vault.id, **(base | overrides))
    result = await RoomService().upgrade_room(db_session=async_session, room_id=room.id)
    assert result is room
    assert room.tier == expected_tier
    assert vault.bottle_caps == 100_000 - expected_cost


async def test_upgrade_keeps_merged_size_and_scales_capacity(async_session: AsyncSession, vault: Vault) -> None:
    await _funded(async_session, vault)
    room = await _create_room(
        async_session,
        vault.id,
        name="Radio studio",
        capacity=30,
        output=60,
        size=9,
        size_min=3,
        size_max=9,
        category=RoomTypeEnum.CAPACITY,
    )
    await RoomService().upgrade_room(db_session=async_session, room_id=room.id)
    assert room.size == 9
    assert room.capacity == 36
    assert room.output == 72
    assert room.image_url == get_room_image_url("Radio studio", tier=2, size=9)
    assert vault.bottle_caps == 100_000 - 1500
