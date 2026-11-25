"""Distance is settled from the path a spatial run actually walked.

Spatial journeys move through the world snapshot: they update `pos_x`/`pos_y` and append to `trail`,
and never touch `total_distance` — only the legacy event generator increments that. Every dispatch
run therefore reported "0 miles" in its completion report, however far it travelled.
"""

from __future__ import annotations

from uuid import uuid4

from app.models.exploration import Exploration
from app.services.exploration.rewards_service import RewardsService


def _exploration(**overrides: object) -> Exploration:
    data: dict[str, object] = {
        "vault_id": uuid4(),
        "dweller_id": uuid4(),
        "duration": 4,
        "dweller_strength": 5,
        "dweller_perception": 5,
        "dweller_endurance": 5,
        "dweller_charisma": 5,
        "dweller_intelligence": 5,
        "dweller_agility": 5,
        "dweller_luck": 5,
    }
    data.update(overrides)
    return Exploration(**data)  # type: ignore[arg-type]


def test_round_trip_counts_the_path_twice() -> None:
    exploration = _exploration(
        world_version=1,
        origin_x=10.0,
        origin_y=10.0,
        pos_x=10.0,
        pos_y=10.0,
        return_started_at=None,
        trail=[
            {"x": 10.0, "y": 10.0, "t": "2026-01-01T00:00:00"},
            {"x": 40.0, "y": 10.0, "t": "2026-01-01T01:00:00"},
            {"x": 70.0, "y": 10.0, "t": "2026-01-01T02:00:00"},
        ],
    )
    exploration.return_started_at = None
    # Outbound only: the run never came home, so it covered 60 units.
    assert RewardsService._journey_distance(exploration) == 60

    exploration.return_started_at = exploration.start_time
    # With a return leg the journey retraces the same line: 120 miles.
    assert RewardsService._journey_distance(exploration) == 120


def test_farthest_point_wins_over_wandering_back() -> None:
    exploration = _exploration(
        world_version=1,
        origin_x=0.0,
        origin_y=0.0,
        trail=[
            {"x": 0.0, "y": 0.0, "t": "2026-01-01T00:00:00"},
            {"x": 30.0, "y": 40.0, "t": "2026-01-01T01:00:00"},
            {"x": 0.0, "y": 10.0, "t": "2026-01-01T02:00:00"},
        ],
    )
    # 3-4-5: the farthest point is 50 units out.
    assert RewardsService._journey_distance(exploration) == 50


def test_legacy_runs_keep_the_distance_they_already_have() -> None:
    exploration = _exploration(total_distance=17, trail=[{"x": 0.0, "y": 0.0, "t": "now"}])
    assert RewardsService._journey_distance(exploration) == 17


def test_a_run_without_a_trail_keeps_its_distance() -> None:
    exploration = _exploration(world_version=1, origin_x=1.0, origin_y=1.0, total_distance=0)
    assert RewardsService._journey_distance(exploration) == 0


def test_an_existing_larger_distance_is_never_reduced() -> None:
    exploration = _exploration(
        world_version=1,
        origin_x=0.0,
        origin_y=0.0,
        total_distance=500,
        trail=[{"x": 10.0, "y": 0.0, "t": "2026-01-01T00:00:00"}],
    )
    assert RewardsService._journey_distance(exploration) == 500
