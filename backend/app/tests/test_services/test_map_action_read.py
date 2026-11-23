from __future__ import annotations

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
    state = SimpleNamespace(searched_at=utcnow() if searched else None)
    assert _action_for(state, location, unlocked=unlocked) == expected
