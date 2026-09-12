"""Tests for CRUDRoom persistence helpers and RoomService orchestration (mocked sessions)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.game_config import GRID_X_MAX, GRID_X_MIN, GRID_Y_MAX, GRID_Y_MIN
from app.crud.base import CRUDBase
from app.crud.room import CRUDRoom
from app.models.room import Room
from app.schemas.common import RoomActionEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate, RoomUpdate
from app.services.room_service import RoomService
from app.utils.exceptions import (
    InsufficientResourcesException,
    NoSpaceAvailableException,
    ResourceNotFoundException,
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
            pytest.param(
                {"coordinate_x": GRID_X_MAX, "size_min": 3}, "Room exceeds grid width", id="exceeds-grid-width"
            ),
            pytest.param({"coordinate_x": 2, "coordinate_y": GRID_Y_MIN - 1}, "Invalid Y coordinate", id="y-below-min"),
            pytest.param({"coordinate_x": 2, "coordinate_y": GRID_Y_MAX + 1}, "Invalid Y coordinate", id="y-above-max"),
        ],
    )
    @pytest.mark.asyncio
    async def test_build_rejects_invalid_input(self, mock_session, overrides: dict, message: str) -> None:
        """_build() rejects malformed size/coordinate input before touching the session."""
        base = _make_room_create()
        room_in = RoomCreate.model_construct(**{**base.model_dump(exclude=set(overrides)), **overrides})

        with pytest.raises(ValueError, match=message):
            await RoomService()._build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_vault_door_already_exists(self, mock_session):
        room_in = _make_room_create(name="Vault Door", coordinate_x=1, coordinate_y=1)
        vault_mock = MagicMock()
        vault_mock.id = room_in.vault_id

        with (
            patch("app.crud.vault.vault.get", new_callable=AsyncMock, return_value=vault_mock),
            patch(
                "app.crud.room.room.get_existing_room_names",
                new_callable=AsyncMock,
                return_value={"vault door"},
            ),
            patch("app.services.room_service.room_rules.validate_build_placement", new_callable=AsyncMock),
        ):
            mock_session.execute.return_value = _make_mock_execute_result(scalars_first=_make_room(name="Vault Door"))

            with pytest.raises(UniqueRoomViolationException):
                await RoomService()._build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_not_enough_dwellers(self, mock_session):
        room_in = _make_room_create(population_required=20)
        vault_mock = MagicMock()
        vault_mock.id = room_in.vault_id

        with (
            patch("app.crud.vault.vault.get", new_callable=AsyncMock, return_value=vault_mock),
            patch(
                "app.services.vault_service.vault_service.is_enough_dwellers",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("app.services.room_service.room_rules.validate_build_placement", new_callable=AsyncMock),
        ):
            # The room sits on level 2; an elevator on that level passes the
            # elevator gating so this test exercises the dweller check
            level_elevator = _make_room(name="Elevator", vault_id=room_in.vault_id, coordinate_y=2)
            mock_session.execute.return_value = _make_mock_execute_result(scalars_first=level_elevator)

            with pytest.raises(InsufficientResourcesException):
                await RoomService()._build(db_session=mock_session, obj_in=room_in)

    @pytest.mark.asyncio
    async def test_room_exists_at_coordinates_same_name_expand(self, mock_session):
        room_in = _make_room_create(name="Diner", coordinate_x=2, coordinate_y=2, size_min=2)
        vault_mock = MagicMock()
        vault_mock.id = room_in.vault_id
        existing_room = _make_room(name="Diner", coordinate_x=2, coordinate_y=2, tier=1)

        with (
            patch("app.crud.vault.vault.get", new_callable=AsyncMock, return_value=vault_mock),
            patch(
                "app.services.vault_service.vault_service.is_enough_dwellers",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.crud.room.room.get_room_by_coordinates",
                new_callable=AsyncMock,
                return_value=existing_room,
            ),
            patch(
                "app.crud.room.room.expand_room",
                new_callable=AsyncMock,
                return_value=existing_room,
            ) as mock_expand,
            patch("app.services.room_service.room_rules.validate_build_placement", new_callable=AsyncMock),
        ):
            level_elevator = _make_room(name="Elevator", vault_id=room_in.vault_id, coordinate_y=2)
            mock_session.execute.return_value = _make_mock_execute_result(scalars_first=level_elevator)

            result = await RoomService()._build(db_session=mock_session, obj_in=room_in)
            mock_expand.assert_called_once()
            assert result == (existing_room, False)

    @pytest.mark.asyncio
    async def test_room_exists_at_coordinates_different_name(self, mock_session):
        room_in = _make_room_create(name="Diner", coordinate_x=2, coordinate_y=2)
        vault_mock = MagicMock()
        vault_mock.id = room_in.vault_id
        existing_room = _make_room(name="Power Generator", coordinate_x=2, coordinate_y=2, tier=1)

        with (
            patch("app.crud.vault.vault.get", new_callable=AsyncMock, return_value=vault_mock),
            patch(
                "app.services.vault_service.vault_service.is_enough_dwellers",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.crud.room.room.get_room_by_coordinates",
                new_callable=AsyncMock,
                return_value=existing_room,
            ),
            patch("app.services.room_service.room_rules.validate_build_placement", new_callable=AsyncMock),
        ):
            level_elevator = _make_room(name="Elevator", vault_id=room_in.vault_id, coordinate_y=2)
            mock_session.execute.return_value = _make_mock_execute_result(scalars_first=level_elevator)

            with pytest.raises(NoSpaceAvailableException):
                await RoomService()._build(db_session=mock_session, obj_in=room_in)


# =============================================================================
# build - elevator gating
# =============================================================================


class TestBuildElevatorGating:
    """Elevators gate level building: non-elevator rooms need an elevator on
    their level (row 0 is anchored by the vault door), and elevators must be
    stacked directly under another elevator."""

    @pytest.mark.asyncio
    async def test_non_elevator_allowed_with_elevator_on_level(self, mock_session):
        vault_id = uuid4()
        room_in = _make_room_create(name="Diner", vault_id=vault_id, coordinate_x=2, coordinate_y=5)
        level_elevator = _make_room(name="Elevator", vault_id=vault_id, coordinate_x=5, coordinate_y=5, size=1)
        mock_session.execute.return_value = _make_mock_execute_result(
            scalars_first=level_elevator, scalars_all=[level_elevator]
        )

        with (
            patch("app.crud.vault.vault.get", new_callable=AsyncMock, return_value=MagicMock(id=vault_id)),
            patch(
                "app.services.vault_service.vault_service.is_enough_dwellers",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "app.services.vault_service.vault_service.withdraw_caps",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.vault_service.vault_service.recalculate_vault_attributes",
                new_callable=AsyncMock,
            ),
            patch("app.services.room_service.event_bus") as mock_event_bus,
            patch("app.services.room_service.get_room_image_url", return_value="/static/room_images/test.png"),
            patch(
                "app.crud.room.room.get_room_by_coordinates",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.crud.room.room.create",
                new_callable=AsyncMock,
            ) as mock_create,
            patch("app.crud.room.room.check_is_unique_room", new_callable=AsyncMock),
            patch(
                "app.crud.room.room.get_room_build_price",
                new_callable=AsyncMock,
                return_value=100,
            ),
        ):
            mock_event_bus.emit = AsyncMock()
            created_room = _make_room(name="Diner", vault_id=vault_id, coordinate_x=2, coordinate_y=5)
            mock_create.return_value = created_room

            result, created = await RoomService()._build(db_session=mock_session, obj_in=room_in)

            assert result is created_room
            assert created is True


# =============================================================================
# destroy
# =============================================================================


class TestDestroy:
    @pytest.mark.asyncio
    async def test_room_not_found(self, mock_session):
        with (
            patch(
                "app.crud.room.room.get",
                new_callable=AsyncMock,
                side_effect=ResourceNotFoundException(Room, identifier=uuid4()),
            ),
            pytest.raises(ResourceNotFoundException),
        ):
            await RoomService().destroy_room(db_session=mock_session, room_id=uuid4())

    @pytest.mark.asyncio
    async def test_destroy_refund_includes_upgrade_costs(self, mock_session):
        room = _make_room(
            category=RoomTypeEnum.CAPACITY,
            base_cost=200,
            incremental_cost=50,
            tier=3,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
        )
        with (
            patch("app.crud.room.room.get", new_callable=AsyncMock, return_value=room),
            patch("app.utils.room_rules.validate_elevator_destroy", new_callable=AsyncMock),
            patch.object(CRUDBase, "delete", new=AsyncMock(return_value=room)),
            patch("app.crud.vault.vault.get", new_callable=AsyncMock) as mock_vault_get,
            patch(
                "app.services.vault_service.vault_service.deposit_caps",
                new_callable=AsyncMock,
            ) as mock_deposit,
            patch(
                "app.services.vault_service.vault_service.recalculate_vault_attributes",
                new_callable=AsyncMock,
            ),
            patch("app.services.room_service.game_config") as mock_game_config,
        ):
            vault_mock = MagicMock()
            vault_mock.id = room.vault_id
            mock_vault_get.return_value = vault_mock
            mock_game_config.resource.destroy_room_refund_rate = 0.5

            await RoomService().destroy_room(db_session=mock_session, room_id=room.id)

            mock_deposit.assert_called_once()
            call_args = mock_deposit.call_args
            assert call_args.kwargs["amount"] == 1125

    @pytest.mark.asyncio
    async def test_destroy_different_case_vault_door(self, mock_session):
        """Verify that 'VAULT DOOR' (any case) is blocked."""
        vault_door = _make_room(name="VAULT DOOR")

        with (
            patch("app.crud.room.room.get", new_callable=AsyncMock, return_value=vault_door),
            pytest.raises(VaultOperationException, match="Cannot destroy the vault door"),
        ):
            await RoomService().destroy_room(db_session=mock_session, room_id=vault_door.id)


# =============================================================================
# upgrade
# =============================================================================


class TestUpgrade:
    @pytest.mark.asyncio
    async def test_already_at_max_tier(self, mock_session):
        room = _make_room(tier=3, t2_upgrade_cost=500, t3_upgrade_cost=1500)

        with (
            patch("app.crud.room.room.get", new_callable=AsyncMock, return_value=room),
            pytest.raises(VaultOperationException, match="already at maximum tier"),
        ):
            await RoomService().upgrade_room(db_session=mock_session, room_id=room.id)

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
    async def test_successful_upgrade_tier2_to_tier3(self, mock_session):
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

        with (
            patch("app.crud.room.room.get", new_callable=AsyncMock, return_value=room),
            patch("app.crud.room.room.update", new_callable=AsyncMock),
            patch("app.crud.vault.vault.get", new_callable=AsyncMock) as mock_vault_get,
            patch(
                "app.services.vault_service.vault_service.withdraw_caps",
                new_callable=AsyncMock,
            ) as mock_withdraw,
            patch(
                "app.services.vault_service.vault_service.recalculate_vault_attributes",
                new_callable=AsyncMock,
            ),
            patch("app.services.room_service.event_bus") as mock_event_bus,
            patch("app.services.room_service.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            vault_mock = MagicMock()
            vault_mock.id = room.vault_id
            mock_vault_get.return_value = vault_mock
            mock_event_bus.emit = AsyncMock()

            result = await RoomService().upgrade_room(db_session=mock_session, room_id=room.id)

            assert result is room
            assert room.tier == 3
            mock_withdraw.assert_called_once_with(
                db_session=mock_session,
                vault_obj=vault_mock,
                amount=1500,
            )

    @pytest.mark.asyncio
    async def test_upgrade_no_further_tiers_after_max_tier_check(self, mock_session):
        """Room with max_tier=2 (has t2 but no t3_cost) can still upgrade from 1->2."""
        room = _make_room(tier=1, capacity=10, output=None, t2_upgrade_cost=500, t3_upgrade_cost=None)

        with (
            patch("app.crud.room.room.get", new_callable=AsyncMock, return_value=room),
            patch("app.crud.room.room.update", new_callable=AsyncMock),
            patch("app.crud.vault.vault.get", new_callable=AsyncMock) as mock_vault_get,
            patch(
                "app.services.vault_service.vault_service.withdraw_caps",
                new_callable=AsyncMock,
            ) as mock_withdraw,
            patch(
                "app.services.vault_service.vault_service.recalculate_vault_attributes",
                new_callable=AsyncMock,
            ),
            patch("app.services.room_service.event_bus") as mock_event_bus,
            patch("app.services.room_service.get_room_image_url", return_value="/static/room_images/test.png"),
        ):
            vault_mock = MagicMock()
            vault_mock.id = room.vault_id
            mock_vault_get.return_value = vault_mock
            mock_event_bus.emit = AsyncMock()

            result = await RoomService().upgrade_room(db_session=mock_session, room_id=room.id)

            assert result is room
            assert room.tier == 2
            mock_withdraw.assert_called_once_with(
                db_session=mock_session,
                vault_obj=vault_mock,
                amount=500,
            )
