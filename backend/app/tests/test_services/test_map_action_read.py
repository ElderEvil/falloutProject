from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.enums import LocationTypeEnum, PlaceKindEnum
from app.core.game_config import game_config
from app.services.map.reads import _action_for, _purpose_for
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
        # A magazine site is a one-time find like any other: searched once, silent forever.
        ("National Archives", "landmark", True, True, False, "salvage"),
        ("National Archives", "landmark", True, True, True, "none"),
        ("Arefu", "settlement", True, True, False, "none"),
    ],
)
def test_action_for_place(monkeypatch, name, group_key, unlocked, collectibles, searched, expected):
    monkeypatch.setattr(game_config.features, "collectibles", collectibles)
    location = SimpleNamespace(name=name, group_key=group_key, kind=PlaceKindEnum.PLACE)
    state = SimpleNamespace(searched_at=utcnow() if searched else None)
    assert _action_for(state, location, unlocked=unlocked) == expected


@pytest.mark.parametrize(
    ("state_type", "group_key", "expected"),
    [
        (LocationTypeEnum.HOME_VAULT, None, "home"),
        # Trade is the archetype, not the caravan: both market groups stay diamonds.
        (LocationTypeEnum.VISITED, "settlement", "trade"),
        (LocationTypeEnum.VISITED, "city", "trade"),
        # Clearable archetypes are filled circles; non-clearable ones look.
        (LocationTypeEnum.VISITED, "power", "clear"),
        (LocationTypeEnum.DISCOVERY, "landmark", "look"),
    ],
)
def test_purpose_for_place(state_type, group_key, expected):
    location = SimpleNamespace(group_key=group_key, kind=PlaceKindEnum.PLACE)
    assert _purpose_for(state_type, location) == expected


@pytest.mark.parametrize(("emergent_sites", "expected"), [(True, "clear"), (False, "look")])
def test_purpose_for_ungrouped_place_follows_resolved_group(monkeypatch, emergent_sites, expected):
    # Purpose mirrors the same archetype resolver that emits the wire group_key: an emergent
    # ungrouped place resolves to wasteland_site (clearable) when the feature is on, and to no
    # archetype (look) when it is off, so purpose never contradicts group_key.
    monkeypatch.setattr(game_config.features, "emergent_sites", emergent_sites)
    location = SimpleNamespace(group_key=None, kind=PlaceKindEnum.PLACE)
    assert _purpose_for(LocationTypeEnum.VISITED, location) == expected
