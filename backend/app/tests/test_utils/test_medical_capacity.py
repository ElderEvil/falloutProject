"""Tests for compute_medical_capacity helper and MEDICAL_ROOM_PRODUCTION mapping.

Note: The canonical key used in production code is "stimpack" (matching the
Storage model field), not "stimpak" (Fallout universe spelling). All dictionary
keys in capacity maps use "stimpack".
"""

from unittest.mock import MagicMock

from app.core.game_config import MEDICAL_ROOM_PRODUCTION, compute_medical_capacity


def _make_room(name: str, capacity: int | None) -> MagicMock:
    room = MagicMock()
    room.name = name
    room.capacity = capacity
    return room


class TestMedicalRoomProductionMapping:
    """MEDICAL_ROOM_PRODUCTION must correctly identify medical rooms."""

    def test_medbay_maps_to_stimpak(self) -> None:
        assert MEDICAL_ROOM_PRODUCTION.get("medbay") == "stimpack"

    def test_science_lab_maps_to_radaway(self) -> None:
        assert MEDICAL_ROOM_PRODUCTION.get("science lab") == "radaway"

    def test_unknown_room_returns_none(self) -> None:
        assert MEDICAL_ROOM_PRODUCTION.get("living room") is None
        assert MEDICAL_ROOM_PRODUCTION.get("power plant") is None


class TestComputeMedicalCapacity:
    """compute_medical_capacity sums room capacities correctly."""

    def test_no_medical_rooms(self) -> None:
        rooms = [
            _make_room("Living room", 0),
            _make_room("Power plant", 0),
        ]
        result = compute_medical_capacity(rooms)
        assert result == {"stimpack": 0, "radaway": 0}

    def test_one_medbay(self) -> None:
        rooms = [_make_room("Medbay", 30)]
        result = compute_medical_capacity(rooms)
        assert result == {"stimpack": 30, "radaway": 0}

    def test_one_science_lab(self) -> None:
        rooms = [_make_room("Science Lab", 30)]
        result = compute_medical_capacity(rooms)
        assert result == {"stimpack": 0, "radaway": 30}

    def test_medbay_and_science_lab(self) -> None:
        rooms = [
            _make_room("Medbay", 30),
            _make_room("Science Lab", 20),
        ]
        result = compute_medical_capacity(rooms)
        assert result == {"stimpack": 30, "radaway": 20}

    def test_multiple_medbays_sum_capacity(self) -> None:
        rooms = [
            _make_room("Medbay", 30),
            _make_room("Medbay", 30),
        ]
        result = compute_medical_capacity(rooms)
        assert result == {"stimpack": 60, "radaway": 0}

    def test_case_insensitive_matching(self) -> None:
        rooms = [
            _make_room("MedBay", 30),
            _make_room("SCIENCE LAB", 20),
        ]
        result = compute_medical_capacity(rooms)
        assert result == {"stimpack": 30, "radaway": 20}

    def test_room_with_none_capacity_skipped(self) -> None:
        rooms = [_make_room("Medbay", None)]
        result = compute_medical_capacity(rooms)
        assert result == {"stimpack": 0, "radaway": 0}

    def test_upgraded_room_higher_capacity(self) -> None:
        rooms = [_make_room("Medbay", 60)]
        result = compute_medical_capacity(rooms)
        assert result == {"stimpack": 60, "radaway": 0}
