"""Tests for deterministic world-map place utilities."""

from app.utils.places import (
    GENERIC_ORIGIN_SKIP,
    collision_nudge,
    normalize_place_name,
    schematic_coords,
)


class TestCollisionNudge:
    """Tests for collision_nudge."""

    def test_result_within_bounds(self) -> None:
        for base in ((0.0, 0.0), (100.0, 100.0), (50.0, 50.0)):
            result = collision_nudge(base, {base})
            assert result != base
            assert 0.0 <= result[0] <= 100.0
            assert 0.0 <= result[1] <= 100.0
