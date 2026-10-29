"""Tests for CRUDRoom persistence helpers and RoomService orchestration.

Every test drives a real SQLite session and real services; the single exception is
``test_no_upgrade_cost_tier2``, which needs ``t3_upgrade_cost=0`` — a value
``RoomCreate``/``RoomBase`` reject (``ge=1500``) — so it keeps a mock session.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import GRID_X_MAX, GRID_X_MIN, GRID_Y_MAX, GRID_Y_MIN, game_config
from app.crud.room import CRUDRoom
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import RoomActionEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate, RoomUpdate
from app.services.room_service import RoomService
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceNotFoundException,
    UniqueRoomViolationException,
    VaultOperationException,
)
from app.utils.room_assets import get_room_image_url


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
    """Create a Room model instance with defaults."""
    defaults = {
        "id": uuid4(),
        "vault_id": uuid4(),
        "name": "Test Room",
        "category": RoomTypeEnum.PRODUCTION,
        "tier": 1,
        "size": 3,
        "size_min": 3,
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
        "image_url": None,
    }
    defaults.update(overrides)
    return Room(**defaults)


def _make_room_create(**overrides) -> RoomCreate:
    """Create a RoomCreate schema instance with defaults."""
    defaults = {
        "vault_id": uuid4(),
        "name": "Test Room",
        "category": RoomTypeEnum.PRODUCTION,
        "tier": 1,
        "size": 3,
        "size_min": 1,
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
    defaults.update(overrides)
    return RoomCreate(**defaults)


async def _create_room(session: AsyncSession, vault_id, **overrides) -> Room:
    """Persist a real Room row so the CRUD queries under test run actual SQL."""
    room_in = _make_room_create(vault_id=vault_id, **overrides)
    return await crud.room.create(db_session=session, obj_in=room_in)


# =============================================================================
# evaluate_capacity_formula
# =============================================================================


class TestEvaluateCapacityFormula:
    def test_unknown_name_is_rejected(self, room_crud):
        """Formulas may only refer to the backend-owned L and S variables."""
        assert room_crud.evaluate_capacity_formula("S / unknown_var", level=3, size=5) == 0


# =============================================================================
# evaluate_output_formula
# =============================================================================


class TestEvaluateOutputFormula:
    def test_value_error(self, room_crud):
        result = room_crud.evaluate_output_formula("int('abc')", level=3, size=5)
        assert result == 0


# =============================================================================
# requires_recalculation
# =============================================================================


# =============================================================================
# get_multy_by_vault
# =============================================================================


class TestGetMultyByVault:
    @pytest.mark.asyncio
    async def test_returns_rooms(self, room_crud, async_session: AsyncSession, vault: Vault):
        created = {
            (await _create_room(async_session, vault.id, name="Diner", coordinate_x=1)).id,
            (await _create_room(async_session, vault.id, name="Kitchen", coordinate_x=3)).id,
        }

        result = await room_crud.get_multy_by_vault(db_session=async_session, vault_id=vault.id, skip=0, limit=10)

        assert {room.id for room in result} == created


# =============================================================================
# get_existing_room_names
# =============================================================================


class TestGetExistingRoomNames:
    @pytest.mark.asyncio
    async def test_returns_lowercase_names(self, room_crud, async_session: AsyncSession, vault: Vault):
        await _create_room(async_session, vault.id, name="Living Room", coordinate_x=1)
        await _create_room(async_session, vault.id, name="DINER", coordinate_x=3)
        await _create_room(async_session, vault.id, name="Elevator", coordinate_x=5)

        result = await room_crud.get_existing_room_names(db_session=async_session, vault_id=vault.id)

        assert result == {"living room", "diner", "elevator"}


# =============================================================================
# get_room_by_coordinates
# =============================================================================


# =============================================================================
# get_room_build_price
# =============================================================================


class TestGetRoomBuildPrice:
    @pytest.mark.asyncio
    async def test_zero_incremental_cost_prices_at_base_cost(
        self, room_crud, async_session: AsyncSession, vault: Vault
    ):
        """A unique room (zero/null incremental cost) is priced at its base cost.

        Supersedes the old ``test_zero_incremental_cost_raises_value_error`` raise
        contract: ``RoomBase.is_unique`` defines zero/null incremental cost as the
        unique-room marker, so a unique room must charge its base price (issue #997).
        """
        room_in = _make_room_create(vault_id=vault.id, base_cost=100, incremental_cost=0)
        assert room_in.is_unique is True

        price = await room_crud.get_room_build_price(db_session=async_session, room_in=room_in)

        assert price == 100

    @pytest.mark.asyncio
    async def test_unique_room_ignores_existing_room_count(self, room_crud, async_session: AsyncSession, vault: Vault):
        """Zero/null incremental cost applies no per-room increment, even with same-category rooms built."""
        await _create_room(async_session, vault.id, category=RoomTypeEnum.PRODUCTION, coordinate_x=1)
        await _create_room(async_session, vault.id, category=RoomTypeEnum.PRODUCTION, coordinate_x=3)
        room_in = _make_room_create(
            vault_id=vault.id, category=RoomTypeEnum.PRODUCTION, base_cost=300, incremental_cost=None
        )
        assert room_in.is_unique is True

        price = await room_crud.get_room_build_price(db_session=async_session, room_in=room_in)

        assert price == 300

    @pytest.mark.asyncio
    async def test_price_counts_only_same_room_type(
        self, room_crud, async_session: AsyncSession, vault: Vault, user_with_vault
    ):
        await _create_room(async_session, vault.id, name="Power Generator", size_min=3, coordinate_x=1)
        await _create_room(async_session, vault.id, name="Power Generator", size_min=3, tier=2, coordinate_x=4)
        await _create_room(async_session, vault.id, name="Diner", coordinate_x=7)
        await _create_room(async_session, vault.id, name="Living room", category=RoomTypeEnum.CAPACITY, coordinate_x=10)
        _, other_vault = user_with_vault
        await _create_room(async_session, other_vault.id, name="Power Generator", size_min=3)
        room_in = _make_room_create(vault_id=vault.id, name="Power Generator", base_cost=100, incremental_cost=25)

        price = await room_crud.get_room_build_price(db_session=async_session, room_in=room_in)

        assert price == 150

    @pytest.mark.parametrize(("size", "expected"), [(None, 125), (3, 125), (6, 150), (9, 175)])
    async def test_price_counts_merged_segments(
        self, room_crud, async_session: AsyncSession, vault: Vault, size, expected
    ):
        await _create_room(async_session, vault.id, name="Power Generator", size_min=3, size=size, size_max=9)
        room_in = _make_room_create(vault_id=vault.id, name="Power Generator", base_cost=100, incremental_cost=25)

        assert await room_crud.get_room_build_price(db_session=async_session, room_in=room_in) == expected


# =============================================================================
# check_is_unique_room
# =============================================================================


class TestCheckIsUniqueRoom:
    @pytest.mark.asyncio
    async def test_unique_room_exists_raises_exception(self, room_crud, async_session: AsyncSession, vault: Vault):
        await _create_room(async_session, vault.id, name="Vault Door", incremental_cost=0, coordinate_x=1)
        room_in = _make_room_create(vault_id=vault.id, name="Vault Door", incremental_cost=0)  # is_unique=True

        with pytest.raises(UniqueRoomViolationException):
            await room_crud.check_is_unique_room(db_session=async_session, obj_in=room_in)


# =============================================================================
# get_adjacent_mergeable_rooms
# =============================================================================


class TestGetAdjacentMergeableRooms:
    @pytest.mark.asyncio
    async def test_finds_right_neighbor(self, room_crud, async_session: AsyncSession, vault: Vault):
        neighbor = await _create_room(
            async_session, vault.id, name="Diner", tier=1, size=3, coordinate_x=5, coordinate_y=2
        )

        result = await room_crud.get_adjacent_mergeable_rooms(
            db_session=async_session,
            vault_id=vault.id,
            name="Diner",
            tier=1,
            coordinate_x=2,
            coordinate_y=2,
            size=3,
        )

        assert [room.id for room in result] == [neighbor.id]

    @pytest.mark.asyncio
    async def test_finds_left_neighbor(self, room_crud, async_session: AsyncSession, vault: Vault):
        neighbor = await _create_room(
            async_session, vault.id, name="Diner", tier=1, size=3, coordinate_x=0, coordinate_y=2
        )

        result = await room_crud.get_adjacent_mergeable_rooms(
            db_session=async_session,
            vault_id=vault.id,
            name="Diner",
            tier=1,
            coordinate_x=3,
            coordinate_y=2,
            size=3,
        )

        assert [room.id for room in result] == [neighbor.id]

    @pytest.mark.asyncio
    async def test_different_name_not_returned(self, room_crud, async_session: AsyncSession, vault: Vault):
        # Footprint touches the candidate, but the name differs, so the filter must exclude it.
        await _create_room(async_session, vault.id, name="Kitchen", tier=1, size=3, coordinate_x=5, coordinate_y=2)

        result = await room_crud.get_adjacent_mergeable_rooms(
            db_session=async_session,
            vault_id=vault.id,
            name="Diner",
            tier=1,
            coordinate_x=2,
            coordinate_y=2,
            size=3,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_different_row_not_returned(self, room_crud, async_session: AsyncSession, vault: Vault):
        # Adjacent along the row axis, but on a different row than the candidate.
        await _create_room(async_session, vault.id, name="Diner", tier=1, size=3, coordinate_x=5, coordinate_y=3)

        result = await room_crud.get_adjacent_mergeable_rooms(
            db_session=async_session,
            vault_id=vault.id,
            name="Diner",
            tier=1,
            coordinate_x=2,
            coordinate_y=2,
            size=3,
        )

        assert result == []


# =============================================================================
# check_elevator_dependencies
# =============================================================================


# =============================================================================
# build
# =============================================================================


class TestBuild:
    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            pytest.param({"size_min": 0, "size_max": 6}, "Invalid room size", id="size-min-below-1"),
            pytest.param({"size_min": None, "size_max": 6}, "Invalid room size", id="size-min-none"),
            pytest.param({"size_min": 5, "size_max": 3}, "Invalid room size", id="size-min-exceeds-max"),
            pytest.param({"size_min": 3, "size_max": None}, "Invalid room size", id="size-max-none"),
            pytest.param(
                {"coordinate_x": None, "coordinate_y": None},
                "Room coordinates must be specified",
                id="coordinates-none",
            ),
            pytest.param({"coordinate_x": GRID_X_MIN - 1, "coordinate_y": 2}, "Invalid X coordinate", id="x-below-min"),
            pytest.param({"coordinate_x": GRID_X_MAX + 1, "coordinate_y": 2}, "Invalid X coordinate", id="x-above-max"),
            pytest.param(
                {"coordinate_x": GRID_X_MAX, "size_min": 3}, "Room exceeds grid width", id="exceeds-grid-width"
            ),
            pytest.param({"coordinate_x": 2, "coordinate_y": GRID_Y_MIN - 1}, "Invalid Y coordinate", id="y-below-min"),
            pytest.param({"coordinate_x": 2, "coordinate_y": GRID_Y_MAX + 1}, "Invalid Y coordinate", id="y-above-max"),
        ],
    )
    @pytest.mark.asyncio
    async def test_build_rejects_invalid_input(
        self, async_session: AsyncSession, vault: Vault, overrides: dict, message: str
    ) -> None:
        """_build() rejects malformed size/coordinate input before any placement or write."""
        base = _make_room_create(vault_id=vault.id)
        room_in = RoomCreate.model_construct(**{**base.model_dump(exclude=set(overrides)), **overrides})

        with pytest.raises(ValueError, match=message):
            await RoomService()._build(db_session=async_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_vault_door_already_exists(self, async_session: AsyncSession, vault: Vault):
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
        room_in = _make_room_create(
            vault_id=vault.id,
            name="Vault Door",
            incremental_cost=0,
            size=1,
            size_min=1,
            coordinate_x=1,
            coordinate_y=0,
        )

        with pytest.raises(UniqueRoomViolationException):
            await RoomService()._build(db_session=async_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_not_enough_dwellers(self, async_session: AsyncSession, vault: Vault):
        await _create_room(async_session, vault.id, name="Elevator", coordinate_x=5, coordinate_y=2, size=1, size_min=1)
        room_in = _make_room_create(vault_id=vault.id, population_required=20)

        with pytest.raises(InsufficientResourcesException):
            await RoomService()._build(db_session=async_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_adjacent_same_name_room_merges(self, async_session: AsyncSession, vault: Vault):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        await _create_room(async_session, vault.id, name="Elevator", coordinate_x=6, coordinate_y=2, size=1, size_min=1)
        survivor = await _create_room(
            async_session, vault.id, name="Diner", tier=1, size=3, size_min=3, coordinate_x=0, coordinate_y=2
        )
        room_in = _make_room_create(vault_id=vault.id, name="Diner", size=3, size_min=3, coordinate_x=3, coordinate_y=2)

        result, created = await RoomService()._build(db_session=async_session, obj_in=room_in)

        assert created is False
        assert result.id == survivor.id
        assert result.size == 6

    @pytest.mark.asyncio
    async def test_unique_room_charges_base_price_and_rejects_second(self, async_session: AsyncSession, vault: Vault):
        """A unique room builds through the real service and charges only its base price;
        a disconnected second unique room of the same name is rejected before any caps are
        charged (issue #997)."""
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 10_000})
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

        # A neighbour makes the second station's cell buildable, but it is not adjacent to
        # the first, so it cannot merge and uniqueness must reject it.
        await _create_room(async_session, vault.id, name="Diner", size=1, size_min=1, coordinate_x=4, coordinate_y=0)
        second = _make_room_create(**{**unique, "coordinate_x": 3})
        with pytest.raises(UniqueRoomViolationException):
            await RoomService()._build(db_session=async_session, obj_in=second)

        assert vault.bottle_caps == 9_500


# =============================================================================
# build - elevator gating
# =============================================================================


class TestBuildElevatorGating:
    """Elevators gate level building: non-elevator rooms need an elevator on
    their level (row 0 is anchored by the vault door), and elevators must be
    stacked directly under another elevator."""

    @pytest.mark.asyncio
    async def test_non_elevator_allowed_with_elevator_on_level(self, async_session: AsyncSession, vault: Vault):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        await _create_room(async_session, vault.id, name="Elevator", coordinate_x=5, coordinate_y=5, size=1, size_min=1)
        room_in = _make_room_create(vault_id=vault.id, name="Diner", coordinate_x=2, coordinate_y=5)

        result, created = await RoomService()._build(db_session=async_session, obj_in=room_in)

        assert result.name == "Diner"
        assert result.coordinate_y == 5
        assert created is True


# =============================================================================
# destroy
# =============================================================================


class TestDestroy:
    @pytest.mark.asyncio
    async def test_room_not_found(self, async_session: AsyncSession):
        with pytest.raises(ResourceNotFoundException):
            await RoomService().destroy_room(db_session=async_session, room_id=uuid4())

    @pytest.mark.asyncio
    async def test_destroy_refund_includes_upgrade_costs(self, async_session: AsyncSession, vault: Vault):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        room = await _create_room(
            async_session,
            vault.id,
            category=RoomTypeEnum.CAPACITY,
            base_cost=200,
            incremental_cost=50,
            tier=3,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size=3,
            size_min=3,
        )

        with patch.object(game_config.resource, "destroy_room_refund_rate", 0.5):
            await RoomService().destroy_room(db_session=async_session, room_id=room.id)

        assert vault.bottle_caps == 100_000 + 1125

    @pytest.mark.asyncio
    async def test_destroy_refund_scales_with_merged_segments(self, async_session: AsyncSession, vault: Vault):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        room = await _create_room(
            async_session,
            vault.id,
            category=RoomTypeEnum.CAPACITY,
            base_cost=200,
            incremental_cost=50,
            tier=1,
            t2_upgrade_cost=None,
            t3_upgrade_cost=None,
            size=9,
            size_min=3,
        )

        with patch.object(game_config.resource, "destroy_room_refund_rate", 0.5):
            await RoomService().destroy_room(db_session=async_session, room_id=room.id)

        assert vault.bottle_caps == 100_000 + 375

    @pytest.mark.asyncio
    async def test_destroy_refund_scales_upgrade_cost_for_merged_segments(
        self, async_session: AsyncSession, vault: Vault
    ):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        room = await _create_room(
            async_session,
            vault.id,
            category=RoomTypeEnum.CAPACITY,
            base_cost=200,
            incremental_cost=50,
            tier=2,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size=9,
            size_min=3,
        )

        with patch.object(game_config.resource, "destroy_room_refund_rate", 0.5):
            await RoomService().destroy_room(db_session=async_session, room_id=room.id)

        assert vault.bottle_caps == 100_000 + 1125

    @pytest.mark.asyncio
    async def test_destroy_different_case_vault_door(self, async_session: AsyncSession, vault: Vault):
        """Verify that 'VAULT DOOR' (any case) is blocked."""
        vault_door = await _create_room(
            async_session, vault.id, name="VAULT DOOR", incremental_cost=0, coordinate_x=0, coordinate_y=0
        )

        with pytest.raises(VaultOperationException, match="Cannot destroy the vault door"):
            await RoomService().destroy_room(db_session=async_session, room_id=vault_door.id)


# =============================================================================
# upgrade
# =============================================================================


class TestUpgrade:
    @pytest.mark.asyncio
    async def test_already_at_max_tier(self, async_session: AsyncSession, vault: Vault):
        room = await _create_room(
            async_session, vault.id, name="Diner", tier=3, t2_upgrade_cost=500, t3_upgrade_cost=1500, coordinate_x=1
        )

        with pytest.raises(VaultOperationException, match="already at maximum tier"):
            await RoomService().upgrade_room(db_session=async_session, room_id=room.id)

    @pytest.mark.asyncio
    async def test_no_upgrade_cost_tier2(self, mock_session):
        """t3_upgrade_cost=0 is falsy (but not None), so max_tier=3 but no valid cost for tier 2."""
        room = _make_room(tier=2, t2_upgrade_cost=500, t3_upgrade_cost=0)

        with (
            patch("app.crud.room.room.get", new_callable=AsyncMock, return_value=room),
            pytest.raises(VaultOperationException, match="No upgrade cost defined"),
        ):
            await RoomService().upgrade_room(db_session=mock_session, room_id=room.id)

    @pytest.mark.asyncio
    async def test_successful_upgrade_tier2_to_tier3(self, async_session: AsyncSession, vault: Vault):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        room = await _create_room(
            async_session,
            vault.id,
            capacity=20,
            output=100,
            size=3,
            size_min=3,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            tier=2,
            category=RoomTypeEnum.CAPACITY,
        )

        result = await RoomService().upgrade_room(db_session=async_session, room_id=room.id)

        assert result is room
        assert room.tier == 3
        assert vault.bottle_caps == 100_000 - 1500

    @pytest.mark.asyncio
    async def test_upgrade_keeps_merged_size_and_scales_capacity(self, async_session: AsyncSession, vault: Vault):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        room = await _create_room(
            async_session,
            vault.id,
            name="Radio studio",
            capacity=30,
            output=60,
            size=9,
            size_min=3,
            size_max=9,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            tier=1,
            category=RoomTypeEnum.CAPACITY,
        )

        await RoomService().upgrade_room(db_session=async_session, room_id=room.id)

        assert room.size == 9
        assert room.capacity == 36
        assert room.output == 72
        assert room.image_url == get_room_image_url("Radio studio", tier=2, size=9)

    @pytest.mark.asyncio
    async def test_upgrade_charges_every_merged_segment(self, async_session: AsyncSession, vault: Vault):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        room = await _create_room(
            async_session,
            vault.id,
            capacity=30,
            output=60,
            size=9,
            size_min=3,
            size_max=9,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            tier=1,
            category=RoomTypeEnum.CAPACITY,
        )

        await RoomService().upgrade_room(db_session=async_session, room_id=room.id)

        assert vault.bottle_caps == 100_000 - 1500

    @pytest.mark.asyncio
    async def test_upgrade_no_further_tiers_after_max_tier_check(self, async_session: AsyncSession, vault: Vault):
        await crud.vault.update(db_session=async_session, id=vault.id, obj_in={"bottle_caps": 100_000})
        room = await _create_room(
            async_session,
            vault.id,
            capacity=10,
            output=None,
            size=3,
            size_min=3,
            t2_upgrade_cost=500,
            t3_upgrade_cost=None,
            tier=1,
        )

        result = await RoomService().upgrade_room(db_session=async_session, room_id=room.id)

        assert result is room
        assert room.tier == 2
        assert vault.bottle_caps == 100_000 - 500
