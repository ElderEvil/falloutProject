"""Serialized exploration history must retain its UTC instant across the cutover."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.core.enums import ExplorationStatus
from app.core.game_config import game_config
from app.models.exploration import Exploration
from app.services.exploration.event_generator import event_generator


@pytest.mark.parametrize("offset_minutes", [None, 0, 345, -240])
@pytest.mark.parametrize("boundary_us", [-1, 0, 1])
def test_event_interval_accepts_legacy_and_offset_history(offset_minutes: int | None, boundary_us: int) -> None:
    now = datetime(2026, 11, 6, 12)
    interval = timedelta(seconds=game_config.exploration.event_interval_seconds)
    last_event = now - interval + timedelta(microseconds=boundary_us)
    if offset_minutes is not None:
        last_event = last_event.replace(tzinfo=UTC).astimezone(timezone(timedelta(minutes=offset_minutes)))
    timestamp = last_event.isoformat()
    if offset_minutes == 0:
        timestamp = timestamp.replace("+00:00", "Z")
    history = [
        {"timestamp": "2020-01-01T00:00:00", "event_id": "legacy:unchanged"},
        {"timestamp": timestamp, "unknown": {"timestamp": "do not rewrite", "id": "cached:event"}},
    ]
    exploration = Exploration(
        vault_id=uuid4(),
        dweller_id=uuid4(),
        duration=4,
        start_time=now - timedelta(hours=1),
        events=deepcopy(history),
        loot_collected=[{"found_at": "2020-01-01T00:00:00", "item": "legacy loot"}],
        trail=[{"t": "2020-01-01T00:00:00", "x": 1, "y": 2}],
        dweller_strength=5,
        dweller_perception=5,
        dweller_endurance=5,
        dweller_charisma=5,
        dweller_intelligence=5,
        dweller_agility=5,
        dweller_luck=5,
    )
    original = deepcopy(exploration.model_dump())

    with patch("app.services.exploration.event_generator.utcnow", return_value=now) as clock:
        assert event_generator.can_generate_event(exploration) is (boundary_us <= 0)
        exploration.status = ExplorationStatus.RETURNING
        assert event_generator.can_generate_event(exploration) is False
        exploration.status = ExplorationStatus.ACTIVE

    assert exploration.model_dump() == original


def test_event_interval_compares_an_aware_clock_with_legacy_history() -> None:
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    interval = timedelta(seconds=game_config.exploration.event_interval_seconds)
    exploration = Exploration(
        vault_id=uuid4(),
        dweller_id=uuid4(),
        duration=4,
        start_time=now - timedelta(hours=1),
        events=[{"timestamp": (now - interval).replace(tzinfo=None).isoformat()}],
        dweller_strength=5,
        dweller_perception=5,
        dweller_endurance=5,
        dweller_charisma=5,
        dweller_intelligence=5,
        dweller_agility=5,
        dweller_luck=5,
    )

    with patch("app.services.exploration.event_generator.utcnow", return_value=now):
        assert event_generator.can_generate_event(exploration) is True
