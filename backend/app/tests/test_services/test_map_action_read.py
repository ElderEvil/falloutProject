"""Map-action derivation for clearable sites and salvage points."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.enums import PlaceKindEnum
from app.core.game_config import game_config
from app.services.map.reads import _action_for
from app.utils.time import utcnow


def _location(name: str, group_key: str | None) -> SimpleNamespace:
    return SimpleNamespace(name=name, group_key=group_key, kind=PlaceKindEnum.PLACE)


def test_clearable_places_offer_clear() -> None:
    assert (
        _action_for(SimpleNamespace(searched_at=None), _location("Poseidon Energy", "power"), unlocked=True) == "clear"
    )


def test_locked_place_offers_nothing() -> None:
    """The dispatch service refuses an unknown place, so the map must not advertise an action."""
    location = _location("Poseidon Energy", "power")

    assert _action_for(SimpleNamespace(searched_at=None), location, unlocked=False) == "none"


def test_inert_place_offers_salvage_only_with_the_flag_and_before_searching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    location = _location("Museum of Freedom", "landmark")

    monkeypatch.setattr(game_config.features, "collectibles", False)
    assert _action_for(SimpleNamespace(searched_at=None), location, unlocked=True) == "none"

    monkeypatch.setattr(game_config.features, "collectibles", True)
    assert _action_for(SimpleNamespace(searched_at=None), location, unlocked=True) == "salvage"
    assert _action_for(SimpleNamespace(searched_at=utcnow()), location, unlocked=True) == "none"


def test_inert_place_without_a_bound_collectible_offers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(game_config.features, "collectibles", True)

    assert _action_for(SimpleNamespace(searched_at=None), _location("Arefu", "settlement"), unlocked=True) == "none"
