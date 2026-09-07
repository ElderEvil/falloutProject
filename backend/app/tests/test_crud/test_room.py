"""Tests for CRUDRoom covering all methods with mocked DB sessions."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.game_config import GRID_X_MAX, GRID_X_MIN, GRID_Y_MAX, GRID_Y_MIN
from app.crud.base import CRUDBase
from app.crud.room import CRUDRoom
from app.models.room import Room
from app.schemas.common import RoomActionEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate, RoomUpdate
from app.utils import room_rules
from app.utils.exceptions import (
    InsufficientResourcesException,
    NoSpaceAvailableException,
    UniqueRoomViolationException,
    VaultOperationException,
)


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


def _make_mock_execute_result(scalars_all=None, scalars_first=None, scalar_one=None):
    """Build a mock for: result = await session.execute(...); result.scalars().all()/.first()

    Always configures result.scalars() to return a mock with .all() and .first().
    Pass scalars_all and scalars_first as desired, including None for empty results.
    """
    scalars_result = MagicMock()
    scalars_result.all.return_value = scalars_all
    scalars_result.first.return_value = scalars_first

    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars_result)
    if scalar_one is not None:
        result.scalar_one.return_value = scalar_one
    return result


def _make_room(**overrides) -> Room:
    """Create a Room model instance with defaults."""
    defaults = {
        "id": uuid4(),
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
        "image_url": None,
        "speedup_multiplier": 1.0,
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
    async def test_returns_rooms(self, room_crud, mock_session):
        vault_id = uuid4()
        expected_rooms = [_make_room(vault_id=vault_id), _make_room(vault_id=vault_id)]
        mock_session.execute.return_value = _make_mock_execute_result(scalars_all=expected_rooms)

        result = await room_crud.get_multy_by_vault(db_session=mock_session, vault_id=vault_id, skip=0, limit=10)
        assert result == expected_rooms
        mock_session.execute.assert_called_once()


# =============================================================================
# get_existing_room_names
# =============================================================================


class TestGetExistingRoomNames:
    @pytest.mark.asyncio
    async def test_returns_lowercase_names(self, room_crud, mock_session):
        vault_id = uuid4()
        mock_session.execute.return_value = _make_mock_execute_result(scalars_all=["Living Room", "DINER", "Elevator"])

        result = await room_crud.get_existing_room_names(db_session=mock_session, vault_id=vault_id)
        assert result == {"living room", "diner", "elevator"}


# =============================================================================
# get_room_by_coordinates
# =============================================================================


# =============================================================================
# get_room_build_price
# =============================================================================


class TestGetRoomBuildPrice:
    @pytest.mark.asyncio
    async def test_zero_incremental_cost_raises_value_error(self, room_crud, mock_session):
        """incremental_cost=0 is falsy, so `not room_in.incremental_cost` is True -> raises."""
        room_in = _make_room_create(base_cost=100, incremental_cost=0)
        mock_session.execute.return_value = _make_mock_execute_result(scalars_all=[])

        with pytest.raises(ValueError, match="Incremental cost must be set"):
            await room_crud.get_room_build_price(db_session=mock_session, room_in=room_in)


# =============================================================================
# check_is_unique_room
# =============================================================================


class TestCheckIsUniqueRoom:
    @pytest.mark.asyncio
    async def test_unique_room_exists_raises_exception(self, room_crud, mock_session):
        room_in = _make_room_create(incremental_cost=0, name="Vault Door")  # is_unique=True
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=_make_room(name="Vault Door"))

        with pytest.raises(UniqueRoomViolationException):
            await room_crud.check_is_unique_room(db_session=mock_session, obj_in=room_in)


# =============================================================================
# expand_room
# =============================================================================


class TestExpandRoom:
    @pytest.mark.asyncio
    async def test_valid_expansion(self, room_crud, mock_session):
        room = _make_room(size_min=2, size_max=6)
        room_crud.update = AsyncMock(return_value=room)

        result = await room_crud.expand_room(db_session=mock_session, existing_room=room, additional_size=3)
        assert result.size_min == 5
        room_crud.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_exceeds_max_size(self, room_crud, mock_session):
        room = _make_room(size_min=4, size_max=6)

        with pytest.raises(InsufficientResourcesException):
            await room_crud.expand_room(db_session=mock_session, existing_room=room, additional_size=5)


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
            pytest.param({"coordinate_x": 8, "size_min": 3}, "Room exceeds grid width", id="exceeds-grid-width"),
            pytest.param({"coordinate_x": 2, "coordinate_y": GRID_Y_MIN - 1}, "Invalid Y coordinate", id="y-below-min"),
            pytest.param({"coordinate_x": 2, "coordinate_y": GRID_Y_MAX + 1}, "Invalid Y coordinate", id="y-above-max"),
        ],
    )
    @pytest.mark.asyncio
    async def test_build_rejects_invalid_input(self, room_crud, mock_session, overrides: dict, message: str) -> None:
        """build() rejects malformed size/coordinate input before touching the session."""
        base = _make_room_create()
        room_in = RoomCreate.model_construct(**{**base.model_dump(exclude=set(overrides)), **overrides})

        with pytest.raises(ValueError, match=message):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_vault_door_already_exists(self, room_crud, mock_session):
        room_in = _make_room_create(name="Vault Door", coordinate_x=1, coordinate_y=1)
        vault_mock = MagicMock()
        vault_mock.id = room_in.vault_id

        with patch("app.crud.room.vault_crud") as mock_vault_crud:
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            # vault door exists
            mock_session.execute.return_value = _make_mock_execute_result(scalars_first=_make_room(name="Vault Door"))

            with pytest.raises(UniqueRoomViolationException):
                await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_not_enough_dwellers(self, room_crud, mock_session):
        room_in = _make_room_create(population_required=20)
        vault_mock = MagicMock()
        vault_mock.id = room_in.vault_id

        with patch("app.crud.room.vault_crud") as mock_vault_crud:
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.is_enough_dwellers = AsyncMock(return_value=False)
            # The room sits on level 2; an elevator on that level passes the
            # elevator gating so this test exercises the dweller check
            level_elevator = _make_room(name="Elevator", vault_id=room_in.vault_id, coordinate_y=2)
            mock_session.execute.return_value = _make_mock_execute_result(scalars_first=level_elevator)

            with pytest.raises(InsufficientResourcesException):
                await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_room_exists_at_coordinates_same_name_expand(self, room_crud, mock_session):
        room_in = _make_room_create(name="Diner", coordinate_x=2, coordinate_y=2, size_min=2)
        vault_mock = MagicMock()
        vault_mock.id = room_in.vault_id
        existing_room = _make_room(name="Diner", coordinate_x=2, coordinate_y=2, tier=1)

        with patch("app.crud.room.vault_crud") as mock_vault_crud:
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.is_enough_dwellers = AsyncMock(return_value=True)
            level_elevator = _make_room(name="Elevator", vault_id=room_in.vault_id, coordinate_y=2)
            mock_session.execute.return_value = _make_mock_execute_result(scalars_first=level_elevator)

            room_crud.get_room_by_coordinates = AsyncMock(return_value=existing_room)
            room_crud.expand_room = AsyncMock(return_value=existing_room)

            result = await room_crud.build(db_session=mock_session, obj_in=room_in)
            room_crud.expand_room.assert_called_once()
            assert result is existing_room

    @pytest.mark.asyncio
    async def test_room_exists_at_coordinates_different_name(self, room_crud, mock_session):
        room_in = _make_room_create(name="Diner", coordinate_x=2, coordinate_y=2)
        vault_mock = MagicMock()
        vault_mock.id = room_in.vault_id
        existing_room = _make_room(name="Power Generator", coordinate_x=2, coordinate_y=2, tier=1)

        with patch("app.crud.room.vault_crud") as mock_vault_crud:
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.is_enough_dwellers = AsyncMock(return_value=True)
            level_elevator = _make_room(name="Elevator", vault_id=room_in.vault_id, coordinate_y=2)
            mock_session.execute.return_value = _make_mock_execute_result(scalars_first=level_elevator)
            room_crud.get_room_by_coordinates = AsyncMock(return_value=existing_room)

            with pytest.raises(NoSpaceAvailableException):
                await room_crud.build(db_session=mock_session, obj_in=room_in)


# =============================================================================
# build - elevator gating
# =============================================================================


class TestBuildElevatorGating:
    """Elevators gate level building: non-elevator rooms need an elevator on
    their level (row 0 is anchored by the vault door), and elevators must be
    stacked directly under another elevator."""

    @pytest.mark.asyncio
    async def test_non_elevator_allowed_with_elevator_on_level(self, room_crud, mock_session):
        vault_id = uuid4()
        room_in = _make_room_create(name="Diner", vault_id=vault_id, coordinate_x=2, coordinate_y=5)
        level_elevator = _make_room(name="Elevator", vault_id=vault_id, coordinate_x=0, coordinate_y=5)
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=level_elevator)

        with (
            patch("app.crud.room.vault_crud") as mock_vault_crud,
            patch("app.crud.room.event_bus") as mock_event_bus,
            patch("app.crud.room.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            mock_vault_crud.get = AsyncMock(return_value=MagicMock(id=vault_id))
            mock_vault_crud.is_enough_dwellers = AsyncMock(return_value=True)
            mock_vault_crud.withdraw_caps = AsyncMock()
            mock_vault_crud.recalculate_vault_attributes = AsyncMock()
            mock_event_bus.emit = AsyncMock()

            created_room = _make_room(name="Diner", vault_id=vault_id, coordinate_x=2, coordinate_y=5)
            room_crud.get_room_by_coordinates = AsyncMock(return_value=None)
            room_crud.create = AsyncMock(return_value=created_room)
            room_crud.check_is_unique_room = AsyncMock()
            room_crud.get_room_build_price = AsyncMock(return_value=100)

            result = await room_crud.build(db_session=mock_session, obj_in=room_in)

            assert result is created_room


# =============================================================================
# destroy
# =============================================================================


class TestDestroy:
    @pytest.mark.asyncio
    async def test_room_not_found(self, room_crud, mock_session):
        room_crud.get = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match=r"Room with id .* not found"):
            await room_crud.destroy(db_session=mock_session, id=uuid4())

    @pytest.mark.asyncio
    async def test_destroy_refund_includes_upgrade_costs(self, room_crud, mock_session):
        room = _make_room(
            category=RoomTypeEnum.CAPACITY,
            base_cost=200,
            incremental_cost=50,
            tier=3,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
        )
        room_crud.get = AsyncMock(return_value=room)
        with (
            patch("app.crud.room.room_rules.validate_elevator_destroy", new=AsyncMock()),
            patch.object(CRUDBase, "delete", new=AsyncMock(return_value=room)),
            patch("app.crud.room.vault_crud") as mock_vault_crud,
            patch("app.crud.room.game_config") as mock_game_config,
        ):
            vault_mock = MagicMock()
            vault_mock.id = room.vault_id
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.deposit_caps = AsyncMock()
            mock_vault_crud.recalculate_vault_attributes = AsyncMock()
            mock_game_config.resource.destroy_room_refund_rate = 0.5

            await room_crud.destroy(db_session=mock_session, id=room.id)

            mock_vault_crud.deposit_caps.assert_called_once()
            call_args = mock_vault_crud.deposit_caps.call_args
            assert call_args.kwargs["amount"] == 1125

    @pytest.mark.asyncio
    async def test_destroy_different_case_vault_door(self, room_crud, mock_session):
        """Verify that 'VAULT DOOR' (any case) is blocked."""
        vault_door = _make_room(name="VAULT DOOR")
        room_crud.get = AsyncMock(return_value=vault_door)

        with pytest.raises(ValueError, match="Cannot destroy the vault door"):
            await room_crud.destroy(db_session=mock_session, id=vault_door.id)


# =============================================================================
# upgrade
# =============================================================================


class TestUpgrade:
    @pytest.mark.asyncio
    async def test_already_at_max_tier(self, room_crud, mock_session):
        room = _make_room(tier=3, t2_upgrade_cost=500, t3_upgrade_cost=1500)
        room_crud.get = AsyncMock(return_value=room)

        with pytest.raises(ValueError, match="already at maximum tier"):
            await room_crud.upgrade(db_session=mock_session, room_id=room.id)

    @pytest.mark.asyncio
    async def test_no_upgrade_cost_tier2(self, room_crud, mock_session):
        """t3_upgrade_cost=0 is falsy (but not None), so max_tier=3 but no valid cost for tier 2."""
        room = _make_room(tier=2, t2_upgrade_cost=500, t3_upgrade_cost=0)
        room_crud.get = AsyncMock(return_value=room)

        with pytest.raises(ValueError, match="No upgrade cost defined"):
            await room_crud.upgrade(db_session=mock_session, room_id=room.id)

    @pytest.mark.asyncio
    async def test_successful_upgrade_tier2_to_tier3(self, room_crud, mock_session):
        room = _make_room(
            tier=2,
            capacity=20,
            output=100,
            size=3,
            size_min=1,
            size_max=6,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            category=RoomTypeEnum.CAPACITY,
        )
        room_crud.get = AsyncMock(return_value=room)
        room_crud.update = AsyncMock()

        with (
            patch("app.crud.room.vault_crud") as mock_vault_crud,
            patch("app.crud.room.event_bus") as mock_event_bus,
            patch("app.crud.room.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            vault_mock = MagicMock()
            vault_mock.id = room.vault_id
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.withdraw_caps = AsyncMock()
            mock_vault_crud.recalculate_vault_attributes = AsyncMock()
            mock_event_bus.emit = AsyncMock()

            result = await room_crud.upgrade(db_session=mock_session, room_id=room.id)

            assert result is room
            assert room.tier == 3
            mock_vault_crud.withdraw_caps.assert_called_once_with(
                db_session=mock_session,
                vault_obj=vault_mock,
                amount=1500,
            )

    @pytest.mark.asyncio
    async def test_upgrade_no_further_tiers_after_max_tier_check(self, room_crud, mock_session):
        """Room with max_tier=2 (has t2 but no t3_cost) can still upgrade from 1->2."""
        room = _make_room(tier=1, capacity=10, output=None, t2_upgrade_cost=500, t3_upgrade_cost=None)
        room_crud.get = AsyncMock(return_value=room)
        room_crud.update = AsyncMock()

        with (
            patch("app.crud.room.vault_crud") as mock_vault_crud,
            patch("app.crud.room.event_bus") as mock_event_bus,
            patch("app.crud.room.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            vault_mock = MagicMock()
            vault_mock.id = room.vault_id
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.withdraw_caps = AsyncMock()
            mock_vault_crud.recalculate_vault_attributes = AsyncMock()
            mock_event_bus.emit = AsyncMock()

            result = await room_crud.upgrade(db_session=mock_session, room_id=room.id)

            assert result is room
            assert room.tier == 2
            mock_vault_crud.withdraw_caps.assert_called_once_with(
                db_session=mock_session,
                vault_obj=vault_mock,
                amount=500,
            )
