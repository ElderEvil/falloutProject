"""Serialized exploration history must retain its UTC instant across the cutover."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.core.enums import ExplorationStatus
from app.core.game_config import game_config
from app.models.exploration import Exploration
from app.schemas.exploration_event import DangerEventSchema, RestEventSchema
from app.services.exploration.event_generator import event_generator

NOW = datetime(2026, 11, 6, 12)
INTERVAL = timedelta(seconds=game_config.exploration.event_interval_seconds)
SPECIAL = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")


def _exploration(start_time: datetime, **overrides) -> Exploration:
    return Exploration(
        vault_id=uuid4(),
        dweller_id=uuid4(),
        duration=4,
        start_time=start_time,
        **{f"dweller_{key}": 5 for key in SPECIAL},
        **overrides,
    )


@pytest.mark.parametrize("offset_minutes", [None, 0, 345, -240])
@pytest.mark.parametrize("boundary_us", [-1, 0, 1])
def test_event_interval_accepts_legacy_and_offset_history(offset_minutes: int | None, boundary_us: int) -> None:
    last_event = NOW - INTERVAL + timedelta(microseconds=boundary_us)
    if offset_minutes is not None:
        last_event = last_event.replace(tzinfo=UTC).astimezone(timezone(timedelta(minutes=offset_minutes)))
    timestamp = last_event.isoformat().replace("+00:00", "Z") if offset_minutes == 0 else last_event.isoformat()
    history = [
        {"timestamp": "2020-01-01T00:00:00", "event_id": "legacy:unchanged"},
        {"timestamp": timestamp, "unknown": {"timestamp": "do not rewrite", "id": "cached:event"}},
    ]
    exploration = _exploration(
        NOW - timedelta(hours=1),
        events=deepcopy(history),
        loot_collected=[{"found_at": "2020-01-01T00:00:00", "item": "legacy loot"}],
        trail=[{"t": "2020-01-01T00:00:00", "x": 1, "y": 2}],
    )
    original = deepcopy(exploration.model_dump())
    with patch("app.services.exploration.event_generator.utcnow", return_value=NOW):
        assert event_generator.can_generate_event(exploration) is (boundary_us <= 0)
        exploration.status = ExplorationStatus.RETURNING
        assert event_generator.can_generate_event(exploration) is False
        exploration.status = ExplorationStatus.ACTIVE
    assert exploration.model_dump() == original


def test_event_interval_compares_an_aware_clock_with_legacy_history() -> None:
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    exploration = _exploration(
        now - timedelta(hours=1), events=[{"timestamp": (now - INTERVAL).replace(tzinfo=None).isoformat()}]
    )
    with patch("app.services.exploration.event_generator.utcnow", return_value=now):
        assert event_generator.can_generate_event(exploration) is True


def _ready(**overrides) -> Exploration:
    return _exploration(NOW.replace(tzinfo=UTC) - timedelta(hours=1), **overrides)


def _patched(**stubs):
    gen = "app.services.exploration.event_generator"
    patches = [patch(f"{gen}.utcnow", return_value=NOW), patch(f"{gen}.random.random", return_value=1.0)]
    patches += [patch(f"{gen}.random.{name}", return_value=value) for name, value in stubs.items()]
    return patches


@pytest.mark.parametrize(
    ("template", "field", "expected"),
    [("Radiation surge {damage}", "radiation_gain", 7), ("Ambush for {damage}", "health_loss", 5)],
)
def test_generated_danger_event_scales_with_endurance(template: str, field: str, expected: int) -> None:
    patches = _patched(choices=["danger"], choice=template)
    for p in patches:
        p.start()
    try:
        event = event_generator.generate_event(_ready())
    finally:
        for p in patches:
            p.stop()
    assert isinstance(event, DangerEventSchema)
    assert getattr(event, field) == expected


def test_generated_rest_event_adds_the_intelligence_bonus() -> None:
    cfg = game_config.exploration
    patches = _patched(choices=["rest"], choice="Rested for {health}", randint=cfg.rest_health_min)
    for p in patches:
        p.start()
    try:
        event = event_generator.generate_event(_ready())
    finally:
        for p in patches:
            p.stop()
    assert isinstance(event, RestEventSchema)
    assert event.health_restored == cfg.rest_health_min + 5 // 3
