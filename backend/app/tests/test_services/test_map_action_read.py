from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.core.enums import PlaceKindEnum
from app.core.game_config import game_config
from app.services.map.reads import _action_for
from app.utils.time import utcnow


@pytest.mark.parametrize(
    ("name", "group_key", "unlocked", "collectibles", "searched", "expected"),
    [
        ("Poseidon Energy", "power", True, False, False, "clear"),
        # The dispatch service refuses an unknown place, so the map must not advertise an action.
        ("Poseidon Energy", "power", False, False, False, "none"),
        ("Museum of Freedom", "landmark", True, False, False, "none"),
        ("Museum of Freedom", "landmark", True, True, False, "salvage"),
        ("Museum of Freedom", "landmark", True, True, True, "none"),
        ("Arefu", "settlement", True, True, False, "none"),
    ],
)
def test_action_for_place(monkeypatch, name, group_key, unlocked, collectibles, searched, expected):
    monkeypatch.setattr(game_config.features, "collectibles", collectibles)
    location = SimpleNamespace(name=name, group_key=group_key, kind=PlaceKindEnum.PLACE)
    state = SimpleNamespace(searched_at=utcnow() if searched else None, last_read_at=None)
    assert _action_for(state, location, unlocked=unlocked) == expected


def test_a_magazine_place_comes_back_after_its_read_cooldown(monkeypatch) -> None:
    """A magazine site is never retired by ``searched_at``; only the fixed 24h read clock gates it."""
    monkeypatch.setattr(game_config.features, "collectibles", True)
    location = SimpleNamespace(name="National Archives", group_key="landmark", kind=PlaceKindEnum.PLACE)
    now = utcnow()

    def action(hours_ago: float | None) -> str:
        last_read_at = None if hours_ago is None else now - timedelta(hours=hours_ago)
        state = SimpleNamespace(searched_at=None, last_read_at=last_read_at)
        return _action_for(state, location, unlocked=True)

    assert action(None) == "salvage"
    assert action(23) == "none"
    assert action(24) == "salvage"
