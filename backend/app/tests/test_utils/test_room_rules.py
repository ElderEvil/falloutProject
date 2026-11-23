from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.enums import RoomTypeEnum
from app.models.room import Room
from app.utils.exceptions import VaultOperationException
from app.utils.room_rules import validate_build_placement, validate_elevator_destroy


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.exec = AsyncMock()
    return session


def _result(*, first=None, all_=None):
    result = MagicMock()
    result.first.return_value = first
    result.all.return_value = all_
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
    return Room(**(defaults | overrides))


@pytest.mark.asyncio
async def test_elevator_requires_an_elevator_above(mock_session):
    mock_session.exec.return_value = _result(first=None)
    with pytest.raises(Exception, match="directly under another elevator"):
        await validate_build_placement(mock_session, uuid4(), "Elevator", 0, 4, 1)
    mock_session.exec.return_value = _result(first=_make_room(name="Elevator"))
    await validate_build_placement(mock_session, uuid4(), "Elevator", 0, 4, 1)
    vault_id = uuid4()
    elevator = _make_room(name="Elevator", coordinate_x=0, coordinate_y=2, size=1, vault_id=vault_id)
    mock_session.exec.side_effect = [_result(first=elevator), _result(all_=[elevator])]
    await validate_build_placement(mock_session, vault_id, "Medbay", 1, 2, 3)
    mock_session.exec.side_effect, mock_session.exec.return_value = None, _result(first=None)
    with pytest.raises(Exception, match="has no elevator"):
        await validate_build_placement(mock_session, uuid4(), "Diner", 2, 5, 3)


@pytest.mark.asyncio
async def test_placement_rejects_overlaps_and_floating_rooms(mock_session):
    vault_id = uuid4()
    elevator = _make_room(name="Elevator", coordinate_x=0, coordinate_y=2, size=1, vault_id=vault_id)
    existing = _make_room(name="Diner", coordinate_x=3, coordinate_y=2, size=3, vault_id=vault_id)
    mock_session.exec.side_effect = [_result(first=elevator), _result(all_=[elevator, existing])]
    with pytest.raises(Exception, match="overlaps Diner"):
        await validate_build_placement(mock_session, vault_id, "Medbay", 4, 2, 3)

    mock_session.exec.side_effect = [_result(first=elevator), _result(all_=[elevator])]
    with pytest.raises(Exception, match="next to another room"):
        await validate_build_placement(mock_session, vault_id, "Medbay", 5, 2, 3)


@pytest.mark.asyncio
async def test_elevator_destroy_rules(async_session, vault, mock_session):
    elevator = _make_room(name="Elevator", coordinate_y=1, coordinate_x=0, vault_id=vault.id, base_cost=100)
    elevator_below = _make_room(name="Elevator", coordinate_y=2, coordinate_x=0, vault_id=vault.id, base_cost=100)
    async_session.add_all([elevator, elevator_below])
    await async_session.flush()
    with pytest.raises(ValueError, match="stacked directly below"):
        await validate_elevator_destroy(async_session, elevator)

    await validate_elevator_destroy(mock_session, _make_room(name="Diner"))
    mock_session.exec.assert_not_called()
    vault_id = uuid4()
    elevator = _make_room(name="Elevator", coordinate_y=5, vault_id=vault_id)
    other_elevator = _make_room(name="Elevator", coordinate_y=5, vault_id=vault_id, id=uuid4())
    mock_session.exec.side_effect = [_result(first=None), _result(all_=[elevator, other_elevator])]
    await validate_elevator_destroy(mock_session, elevator)
    other_room = _make_room(name="Diner", coordinate_y=5, vault_id=vault_id, id=uuid4())
    mock_session.exec.side_effect = [_result(first=None), _result(all_=[elevator]), _result(all_=[other_room])]
    with pytest.raises(ValueError, match="Cannot destroy this elevator"):
        await validate_elevator_destroy(mock_session, elevator)

    occupied = _make_room(name="Diner", coordinate_x=6, coordinate_y=5, vault_id=vault_id)
    mock_session.exec.side_effect = [
        _result(first=_make_room(name="Elevator", coordinate_y=4, vault_id=vault_id)),
        _result(all_=[occupied]),
    ]
    with pytest.raises(VaultOperationException, match="overlaps"):
        await validate_build_placement(mock_session, vault_id, "Elevator", 6, 5, 1)

    occupied = _make_room(name="Diner", coordinate_x=0, coordinate_y=0, tier=2, vault_id=vault_id)
    mock_session.exec.side_effect = [_result(all_=[occupied])]
    with pytest.raises(VaultOperationException, match="overlaps"):
        await validate_build_placement(mock_session, vault_id, "Diner", 0, 0, 3, tier=1)
