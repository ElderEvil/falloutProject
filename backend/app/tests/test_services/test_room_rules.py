"""Tests for room placement rules — elevator stacking and level-access gating."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.room import Room
from app.schemas.common import RoomTypeEnum
from app.services.room_rules import is_elevator, validate_build_placement, validate_elevator_destroy


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_mock_execute_result(scalars_all=None, scalars_first=None):
    scalars_result = MagicMock()
    scalars_result.all.return_value = scalars_all
    scalars_result.first.return_value = scalars_first
    result = MagicMock()
    result.scalars.return_value = scalars_result
    return result


def _make_room(**overrides) -> Room:
    defaults = {
        "id": uuid4(),
        "vault_id": uuid4(),
        "name": "Test Room",
        "category": RoomTypeEnum.PRODUCTION,
        "tier": 1,
        "size": 3,
        "size_min": 1,
        "size_max": 6,
        "coordinate_x": 0,
        "coordinate_y": 1,
    }
    defaults.update(overrides)
    return Room(**defaults)


@pytest.mark.asyncio
async def test_is_elevator_case_insensitive():
    assert is_elevator("Elevator")
    assert is_elevator("elevator")
    assert is_elevator(" ELEVATOR ")
    assert not is_elevator("Diner")
    assert not is_elevator(None)


class TestValidateBuildPlacement:
    @pytest.mark.asyncio
    async def test_elevator_rejected_without_elevator_above(self, mock_session):
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=None)
        with pytest.raises(Exception, match="directly under another elevator"):
            await validate_build_placement(mock_session, uuid4(), "Elevator", 0, 4)

    @pytest.mark.asyncio
    async def test_elevator_allowed_with_elevator_above(self, mock_session):
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=_make_room(name="Elevator"))
        await validate_build_placement(mock_session, uuid4(), "Elevator", 0, 4)

    @pytest.mark.asyncio
    async def test_non_elevator_rejected_without_elevator_on_level(self, mock_session):
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=None)
        with pytest.raises(Exception, match="has no elevator"):
            await validate_build_placement(mock_session, uuid4(), "Diner", 2, 5)

    @pytest.mark.asyncio
    async def test_non_elevator_allowed_with_elevator_on_level(self, mock_session):
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=_make_room(name="Elevator"))
        await validate_build_placement(mock_session, uuid4(), "Diner", 2, 5)

    @pytest.mark.asyncio
    async def test_non_elevator_allowed_on_row_zero_without_elevator(self, mock_session):
        """The vault door anchors row 0, so rooms may be built there without an elevator."""
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=None)
        await validate_build_placement(mock_session, uuid4(), "Diner", 2, 0)
        mock_session.execute.assert_not_called()


class TestValidateElevatorDestroy:
    @pytest.mark.asyncio
    async def test_non_elevator_returns_immediately(self, mock_session):
        room = _make_room(name="Diner")
        await validate_elevator_destroy(mock_session, room)
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_elevator_with_elevator_above_rejects_destroy(self, mock_session):
        """Destroying an elevator that supports another elevator above breaks the stack."""
        elevator = _make_room(name="Elevator", coordinate_y=2, coordinate_x=0)
        elevator_above = _make_room(name="Elevator", coordinate_y=3, coordinate_x=0, id=uuid4())
        mock_session.execute.return_value = _make_mock_execute_result(scalars_first=elevator_above)

        with pytest.raises(ValueError, match="stacked directly above"):
            await validate_elevator_destroy(mock_session, elevator)

    @pytest.mark.asyncio
    async def test_elevator_with_another_elevator_on_level_allowed(self, mock_session):
        vault_id = uuid4()
        elevator = _make_room(name="Elevator", coordinate_y=5, vault_id=vault_id)
        other_elevator = _make_room(name="Elevator", coordinate_y=5, vault_id=vault_id, id=uuid4())
        no_above = _make_mock_execute_result(scalars_first=None)
        all_elevators = _make_mock_execute_result(scalars_all=[elevator, other_elevator])
        mock_session.execute.side_effect = [no_above, all_elevators]

        await validate_elevator_destroy(mock_session, elevator)

    @pytest.mark.asyncio
    async def test_only_elevator_with_no_other_rooms_allowed(self, mock_session):
        vault_id = uuid4()
        elevator = _make_room(name="Elevator", coordinate_y=5, vault_id=vault_id)
        no_above = _make_mock_execute_result(scalars_first=None)
        all_elevators = _make_mock_execute_result(scalars_all=[elevator])
        no_rooms = _make_mock_execute_result(scalars_all=[])
        mock_session.execute.side_effect = [no_above, all_elevators, no_rooms]

        await validate_elevator_destroy(mock_session, elevator)

    @pytest.mark.asyncio
    async def test_only_elevator_with_other_rooms_rejects_destroy(self, mock_session):
        vault_id = uuid4()
        elevator = _make_room(name="Elevator", coordinate_y=5, vault_id=vault_id)
        other_room = _make_room(name="Diner", coordinate_y=5, vault_id=vault_id, id=uuid4())
        no_above = _make_mock_execute_result(scalars_first=None)
        all_elevators = _make_mock_execute_result(scalars_all=[elevator])
        rooms_on_level = _make_mock_execute_result(scalars_all=[other_room])
        mock_session.execute.side_effect = [no_above, all_elevators, rooms_on_level]

        with pytest.raises(ValueError, match="Cannot destroy this elevator"):
            await validate_elevator_destroy(mock_session, elevator)
