"""Tests for CRUDRoom covering all methods with mocked DB sessions."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.constants import GRID_X_MAX, GRID_X_MIN, GRID_Y_MAX, GRID_Y_MIN
from app.crud.base import CRUDBase
from app.crud.room import CRUDRoom
from app.models.room import Room
from app.schemas.common import RoomActionEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate, RoomUpdate
from app.services import room_rules
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
    def test_valid_formula(self, room_crud):
        result = room_crud.evaluate_capacity_formula("L * 2 + S", level=3, size=5)
        assert result == 11  # 3*2 + 5 = 11

    def test_invalid_syntax(self, room_crud):
        result = room_crud.evaluate_capacity_formula("L * ", level=3, size=5)
        assert result == 0

    def test_unknown_name_is_rejected(self, room_crud):
        """Formulas may only refer to the backend-owned L and S variables."""
        assert room_crud.evaluate_capacity_formula("S / unknown_var", level=3, size=5) == 0

    def test_function_call_is_rejected(self, room_crud):
        """Formula expressions cannot call arbitrary Python functions."""
        assert room_crud.evaluate_capacity_formula("__import__('os')", level=3, size=5) == 0

    def test_negative_result(self, room_crud):
        result = room_crud.evaluate_capacity_formula("L - 100", level=3, size=1)
        assert result == -97  # formula returns int result


# =============================================================================
# evaluate_output_formula
# =============================================================================


class TestEvaluateOutputFormula:
    def test_valid_formula(self, room_crud):
        result = room_crud.evaluate_output_formula("L * S * 3", level=2, size=3)
        assert result == 18  # 2*3*3 = 18

    def test_invalid_syntax(self, room_crud):
        result = room_crud.evaluate_output_formula("invalid(", level=3, size=5)
        assert result == 0

    def test_value_error(self, room_crud):
        result = room_crud.evaluate_output_formula("int('abc')", level=3, size=5)
        assert result == 0


# =============================================================================
# requires_recalculation
# =============================================================================


class TestRequiresRecalculation:
    def test_capacity_category(self, room_crud):
        room = _make_room(category=RoomTypeEnum.CAPACITY)
        assert room_crud.requires_recalculation(room) is True

    def test_production_category_non_radio(self, room_crud):
        room = _make_room(category=RoomTypeEnum.PRODUCTION, name="Power Generator")
        assert room_crud.requires_recalculation(room) is True

    def test_production_category_radio_studio(self, room_crud):
        room = _make_room(category=RoomTypeEnum.PRODUCTION, name="Radio studio")
        assert room_crud.requires_recalculation(room) is False

    def test_training_category(self, room_crud):
        room = _make_room(category=RoomTypeEnum.TRAINING)
        assert room_crud.requires_recalculation(room) is False

    def test_misc_category(self, room_crud):
        room = _make_room(category=RoomTypeEnum.MISC)
        assert room_crud.requires_recalculation(room) is False

    def test_with_room_create_schema(self, room_crud):
        room_in = _make_room_create(category=RoomTypeEnum.CAPACITY)
        assert room_crud.requires_recalculation(room_in) is True


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

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, room_crud, mock_session):
        vault_id = uuid4()
        mock_session.execute.return_value = _make_mock_execute_result(scalars_all=[])

        result = await room_crud.get_multy_by_vault(db_session=mock_session, vault_id=vault_id, skip=0, limit=10)
        assert result == []


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

    @pytest.mark.asyncio
    async def test_returns_empty_set(self, room_crud, mock_session):
        vault_id = uuid4()
        mock_session.execute.return_value = _make_mock_execute_result(scalars_all=[])

        result = await room_crud.get_existing_room_names(db_session=mock_session, vault_id=vault_id)
        assert result == set()


# =============================================================================
# get_room_by_coordinates
# =============================================================================


class TestGetRoomByCoordinates:
    @pytest.mark.asyncio
    async def test_found(self, room_crud, mock_session):
        room = _make_room()
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=room)

        result = await room_crud.get_room_by_coordinates(
            db_session=mock_session,
            vault_id=room.vault_id,
            x_coord=room.coordinate_x,
            y_coord=room.coordinate_y,
        )
        assert result is room

    @pytest.mark.asyncio
    async def test_not_found(self, room_crud, mock_session):
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=None)
        result = await room_crud.get_room_by_coordinates(
            db_session=mock_session,
            vault_id=uuid4(),
            x_coord=5,
            y_coord=10,
        )
        assert result is None


# =============================================================================
# get_room_build_price
# =============================================================================


class TestGetRoomBuildPrice:
    @pytest.mark.asyncio
    async def test_no_existing_rooms_same_category(self, room_crud, mock_session):
        room_in = _make_room_create(base_cost=100, incremental_cost=25)
        mock_session.execute.return_value = _make_mock_execute_result(scalars_all=[])

        price = await room_crud.get_room_build_price(db_session=mock_session, room_in=room_in)
        assert price == 100  # base_cost only

    @pytest.mark.asyncio
    async def test_with_existing_rooms(self, room_crud, mock_session):
        room_in = _make_room_create(base_cost=100, incremental_cost=25)
        mock_session.execute.return_value = _make_mock_execute_result(
            scalars_all=[_make_room(), _make_room(), _make_room()]  # 3 existing
        )

        price = await room_crud.get_room_build_price(db_session=mock_session, room_in=room_in)
        assert price == 175  # 100 + 3*25

    @pytest.mark.asyncio
    async def test_missing_incremental_cost_raises_value_error(self, room_crud, mock_session):
        room_in = _make_room_create(base_cost=100, incremental_cost=None)
        mock_session.execute.return_value = _make_mock_execute_result(scalars_all=[])

        with pytest.raises(ValueError, match="Incremental cost must be set"):
            await room_crud.get_room_build_price(db_session=mock_session, room_in=room_in)

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
    async def test_not_unique_room_does_nothing(self, room_crud, mock_session):
        room_in = _make_room_create(incremental_cost=25)  # is_unique=False
        await room_crud.check_is_unique_room(db_session=mock_session, obj_in=room_in)
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_unique_room_not_exists_does_not_raise(self, room_crud, mock_session):
        room_in = _make_room_create(incremental_cost=None)  # is_unique=True
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=None)

        # Should not raise
        await room_crud.check_is_unique_room(db_session=mock_session, obj_in=room_in)

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
    @pytest.mark.asyncio
    async def test_invalid_size_min_below_1(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"size_min", "size_max"}),
            size_min=0,
            size_max=6,
        )
        with pytest.raises(ValueError, match="Invalid room size"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_invalid_size_min_none(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"size_min", "size_max"}),
            size_min=None,
            size_max=6,
        )
        with pytest.raises(ValueError, match="Invalid room size"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_size_min_exceeds_size_max(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"size_min", "size_max"}),
            size_min=5,
            size_max=3,
        )
        with pytest.raises(ValueError, match="Invalid room size"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_size_max_none_size_min_is_set(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"size_min", "size_max"}),
            size_min=3,
            size_max=None,
        )
        with pytest.raises(ValueError, match="Invalid room size"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_coordinates_none(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"coordinate_x", "coordinate_y"}),
            coordinate_x=None,
            coordinate_y=None,
        )
        with pytest.raises(ValueError, match="Room coordinates must be specified"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_x_coord_below_min(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"coordinate_x", "coordinate_y"}),
            coordinate_x=GRID_X_MIN - 1,
            coordinate_y=2,
        )
        with pytest.raises(ValueError, match="Invalid X coordinate"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_x_coord_above_max(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"coordinate_x", "coordinate_y"}),
            coordinate_x=GRID_X_MAX + 1,
            coordinate_y=2,
        )
        with pytest.raises(ValueError, match="Invalid X coordinate"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_room_exceeds_grid_width(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"coordinate_x", "size_min"}),
            coordinate_x=7,
            size_min=3,
        )
        with pytest.raises(ValueError, match="Room exceeds grid width"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_y_coord_below_min(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"coordinate_x", "coordinate_y"}),
            coordinate_x=2,
            coordinate_y=GRID_Y_MIN - 1,
        )
        with pytest.raises(ValueError, match="Invalid Y coordinate"):
            await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_y_coord_above_max(self, room_crud, mock_session):
        base = _make_room_create()
        room_in = RoomCreate.model_construct(
            **base.model_dump(exclude={"coordinate_x", "coordinate_y"}),
            coordinate_x=2,
            coordinate_y=GRID_Y_MAX + 1,
        )
        with pytest.raises(ValueError, match="Invalid Y coordinate"):
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
            # No vault door check triggered (name != "vault door" case-insensitively... actually it checks lower)
            # wait, the vault door check is "obj_in.name.lower() == 'vault door'"
            # Since "Test Room" != "vault door", it won't trigger

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
            room_crud.get_room_by_coordinates = AsyncMock(return_value=existing_room)

            with pytest.raises(NoSpaceAvailableException):
                await room_crud.build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_successful_build_with_capacity_formula(self, room_crud, mock_session):
        vault_id = uuid4()
        room_in = _make_room_create(
            name="Living room",
            vault_id=vault_id,
            category=RoomTypeEnum.CAPACITY,
            tier=1,
            size=3,
            size_min=1,
            size_max=6,
            capacity_formula="2*S/3*(L+4)-2",
            capacity=None,
            output=None,
            output_formula=None,
            base_cost=100,
            incremental_cost=25,
        )
        vault_mock = MagicMock()
        vault_mock.id = vault_id

        created_room = _make_room(
            id=uuid4(),
            vault_id=vault_id,
            name="Living room",
            category=RoomTypeEnum.CAPACITY,
            tier=1,
            size=3,
            size_min=1,
            size_max=6,
            capacity=8,
            output=None,
            base_cost=100,
            incremental_cost=25,
            coordinate_x=2,
            coordinate_y=2,
        )

        with (
            patch("app.crud.room.vault_crud") as mock_vault_crud,
            patch("app.crud.room.event_bus") as mock_event_bus,
            patch("app.crud.room.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.is_enough_dwellers = AsyncMock(return_value=True)
            mock_vault_crud.withdraw_caps = AsyncMock()
            mock_vault_crud.recalculate_vault_attributes = AsyncMock()
            mock_event_bus.emit = AsyncMock()

            room_crud.get_room_by_coordinates = AsyncMock(return_value=None)
            room_crud.create = AsyncMock(return_value=created_room)
            room_crud.evaluate_capacity_formula = MagicMock(return_value=8)
            room_crud.check_is_unique_room = AsyncMock()
            room_crud.get_room_build_price = AsyncMock(return_value=100)

            result = await room_crud.build(db_session=mock_session, obj_in=room_in)

            assert result is created_room
            mock_vault_crud.withdraw_caps.assert_called_once()
            mock_vault_crud.recalculate_vault_attributes.assert_called_once_with(
                db_session=mock_session,
                vault_obj=vault_mock,
                room_obj=created_room,
                action=RoomActionEnum.BUILD,
            )
            mock_event_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_build_no_recalc_needed(self, room_crud, mock_session):
        vault_id = uuid4()
        room_in = _make_room_create(
            name="Radio studio",
            vault_id=vault_id,
            category=RoomTypeEnum.PRODUCTION,
            tier=1,
            size=2,
            size_min=1,
            size_max=3,
            capacity=None,
            output=None,
            capacity_formula=None,
            output_formula=None,
            base_cost=100,
            incremental_cost=25,
        )
        vault_mock = MagicMock()
        vault_mock.id = vault_id

        created_room = _make_room(
            id=uuid4(),
            vault_id=vault_id,
            name="Radio studio",
            category=RoomTypeEnum.PRODUCTION,
            tier=1,
            size=2,
            size_min=1,
            size_max=3,
            capacity=None,
            output=None,
        )

        with (
            patch("app.crud.room.vault_crud") as mock_vault_crud,
            patch("app.crud.room.event_bus") as mock_event_bus,
            patch("app.crud.room.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.is_enough_dwellers = AsyncMock(return_value=True)
            mock_vault_crud.withdraw_caps = AsyncMock()
            mock_vault_crud.recalculate_vault_attributes = AsyncMock()
            mock_event_bus.emit = AsyncMock()

            room_crud.get_room_by_coordinates = AsyncMock(return_value=None)
            room_crud.create = AsyncMock(return_value=created_room)
            room_crud.check_is_unique_room = AsyncMock()
            room_crud.get_room_build_price = AsyncMock(return_value=100)

            result = await room_crud.build(db_session=mock_session, obj_in=room_in)

            assert result is created_room
            mock_vault_crud.recalculate_vault_attributes.assert_not_called()
            mock_event_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_with_output_formula(self, room_crud, mock_session):
        vault_id = uuid4()
        room_in = _make_room_create(
            name="Power Generator",
            vault_id=vault_id,
            category=RoomTypeEnum.PRODUCTION,
            tier=2,
            size=3,
            size_min=1,
            size_max=6,
            capacity_formula=None,
            output_formula="L*S*3",
            capacity=None,
            output=None,
        )
        vault_mock = MagicMock()
        vault_mock.id = vault_id

        created_room = _make_room(
            id=uuid4(),
            vault_id=vault_id,
            name="Power Generator",
            category=RoomTypeEnum.PRODUCTION,
            tier=2,
            size=3,
            output=18,
        )

        with (
            patch("app.crud.room.vault_crud") as mock_vault_crud,
            patch("app.crud.room.event_bus") as mock_event_bus,
            patch("app.crud.room.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.is_enough_dwellers = AsyncMock(return_value=True)
            mock_vault_crud.withdraw_caps = AsyncMock()
            mock_vault_crud.recalculate_vault_attributes = AsyncMock()
            mock_event_bus.emit = AsyncMock()

            room_crud.get_room_by_coordinates = AsyncMock(return_value=None)
            room_crud.create = AsyncMock(return_value=created_room)
            room_crud.evaluate_output_formula = MagicMock(return_value=18)
            room_crud.check_is_unique_room = AsyncMock()
            room_crud.get_room_build_price = AsyncMock(return_value=100)

            result = await room_crud.build(db_session=mock_session, obj_in=room_in)

            assert result is created_room
            assert room_in.output == 18

    @pytest.mark.asyncio
    async def test_build_uses_size_field_when_set(self, room_crud, mock_session):
        """When size is explicitly set, it should be used in capacity formula evaluation."""
        vault_id = uuid4()
        room_in = _make_room_create(
            name="Living room",
            vault_id=vault_id,
            category=RoomTypeEnum.CAPACITY,
            tier=1,
            size=6,
            size_min=1,
            size_max=9,
            capacity_formula="S*L",
            capacity=None,
        )
        vault_mock = MagicMock()
        vault_mock.id = vault_id

        created_room = _make_room(
            id=uuid4(),
            vault_id=vault_id,
            name="Living room",
            category=RoomTypeEnum.CAPACITY,
            tier=1,
            size=6,
            capacity=6,
        )

        with (
            patch("app.crud.room.vault_crud") as mock_vault_crud,
            patch("app.crud.room.event_bus") as mock_event_bus,
            patch("app.crud.room.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            mock_vault_crud.get = AsyncMock(return_value=vault_mock)
            mock_vault_crud.is_enough_dwellers = AsyncMock(return_value=True)
            mock_vault_crud.withdraw_caps = AsyncMock()
            mock_vault_crud.recalculate_vault_attributes = AsyncMock()
            mock_event_bus.emit = AsyncMock()

            room_crud.get_room_by_coordinates = AsyncMock(return_value=None)
            room_crud.create = AsyncMock(return_value=created_room)
            eval_spy = MagicMock(return_value=6)
            room_crud.evaluate_capacity_formula = eval_spy
            room_crud.check_is_unique_room = AsyncMock()
            room_crud.get_room_build_price = AsyncMock(return_value=100)

            await room_crud.build(db_session=mock_session, obj_in=room_in)

            # Should use size=6, not size_min=1
            eval_spy.assert_called_with(room_in.capacity_formula, room_in.tier, 6)


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
    async def test_cannot_destroy_vault_door(self, room_crud, mock_session):
        vault_door = _make_room(name="Vault Door")
        room_crud.get = AsyncMock(return_value=vault_door)

        with pytest.raises(ValueError, match="Cannot destroy the vault door"):
            await room_crud.destroy(db_session=mock_session, id=vault_door.id)

    @pytest.mark.asyncio
    async def test_elevator_dependency_blocks_destroy(self, room_crud, mock_session):
        elevator = _make_room(name="Elevator")
        room_crud.get = AsyncMock(return_value=elevator)

        with (
            patch(
                "app.crud.room.room_rules.validate_elevator_destroy",
                new=AsyncMock(side_effect=ValueError("Cannot destroy this elevator")),
            ),
            pytest.raises(ValueError, match="Cannot destroy this elevator"),
        ):
            await room_crud.destroy(db_session=mock_session, id=elevator.id)

    @pytest.mark.asyncio
    async def test_successful_destroy_with_recalc(self, room_crud, mock_session):
        room = _make_room(category=RoomTypeEnum.CAPACITY, base_cost=100, incremental_cost=25, tier=1)
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

            result = await room_crud.destroy(db_session=mock_session, id=room.id)

            assert result is room
            mock_vault_crud.deposit_caps.assert_called_once()
            call_args = mock_vault_crud.deposit_caps.call_args
            assert call_args.kwargs["amount"] == 62

            mock_vault_crud.recalculate_vault_attributes.assert_called_once_with(
                db_session=mock_session,
                vault_obj=vault_mock,
                room_obj=room,
                action=RoomActionEnum.DESTROY,
            )

    @pytest.mark.asyncio
    async def test_successful_destroy_no_recalc(self, room_crud, mock_session):
        room = _make_room(category=RoomTypeEnum.TRAINING, base_cost=100, incremental_cost=25, tier=1)
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

            result = await room_crud.destroy(db_session=mock_session, id=room.id)

            assert result is room
            mock_vault_crud.recalculate_vault_attributes.assert_not_called()

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
    async def test_destroy_refund_tier2_only(self, room_crud, mock_session):
        room = _make_room(
            category=RoomTypeEnum.CAPACITY,
            base_cost=200,
            incremental_cost=25,
            tier=2,
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

            # Refund: 50% of (200 + 25 + 500) = 362 (t3 not included since tier=2)
            call_args = mock_vault_crud.deposit_caps.call_args
            assert call_args.kwargs["amount"] == 362

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
    async def test_no_upgrade_cost_tier1(self, room_crud, mock_session):
        """t2_upgrade_cost=0 is falsy (but not None), so max_tier=3 via t3 check but no valid cost for tier 1."""
        room = _make_room(tier=1, t2_upgrade_cost=0, t3_upgrade_cost=1500)
        room_crud.get = AsyncMock(return_value=room)

        with pytest.raises(ValueError, match="No upgrade cost defined"):
            await room_crud.upgrade(db_session=mock_session, room_id=room.id)

    @pytest.mark.asyncio
    async def test_no_upgrade_cost_tier2(self, room_crud, mock_session):
        """t3_upgrade_cost=0 is falsy (but not None), so max_tier=3 but no valid cost for tier 2."""
        room = _make_room(tier=2, t2_upgrade_cost=500, t3_upgrade_cost=0)
        room_crud.get = AsyncMock(return_value=room)

        with pytest.raises(ValueError, match="No upgrade cost defined"):
            await room_crud.upgrade(db_session=mock_session, room_id=room.id)

    @pytest.mark.asyncio
    async def test_successful_upgrade_tier1_to_tier2(self, room_crud, mock_session):
        room = _make_room(
            tier=1, capacity=10, output=50, size=3, size_min=1, size_max=6, t2_upgrade_cost=500, t3_upgrade_cost=1500
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
            assert room.tier == 2
            mock_vault_crud.withdraw_caps.assert_called_once_with(
                db_session=mock_session,
                vault_obj=vault_mock,
                amount=500,
            )
            mock_event_bus.emit.assert_called_once()

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
    async def test_upgrade_without_capacity_and_output(self, room_crud, mock_session):
        """Room with no capacity/output should still upgrade without recalculating those."""
        room = _make_room(
            tier=1,
            capacity=None,
            output=None,
            category=RoomTypeEnum.TRAINING,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
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
            assert room.tier == 2
            # No recalculation since TRAINING doesn't require it
            mock_vault_crud.recalculate_vault_attributes.assert_not_called()

    @pytest.mark.asyncio
    async def test_upgrade_with_recalc(self, room_crud, mock_session):
        room = _make_room(
            tier=1,
            capacity=10,
            output=50,
            size=3,
            size_min=1,
            size_max=6,
            category=RoomTypeEnum.PRODUCTION,
            name="Power Generator",
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
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

            await room_crud.upgrade(db_session=mock_session, room_id=room.id)

            mock_vault_crud.recalculate_vault_attributes.assert_called_once_with(
                db_session=mock_session,
                vault_obj=vault_mock,
                room_obj=room,
                action=RoomActionEnum.UPGRADE,
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
