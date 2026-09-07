"""Tests for compute_medical_capacity helper and MEDICAL_ROOM_PRODUCTION mapping.

Note: The canonical key used in production code is "stimpack" (matching the
Storage model field), not "stimpak" (Fallout universe spelling). All dictionary
keys in capacity maps use "stimpack".
"""

from unittest.mock import MagicMock

from app.services.resource_manager import MEDICAL_ROOM_PRODUCTION, compute_medical_capacity


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
