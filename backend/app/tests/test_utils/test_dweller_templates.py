import random

import pytest

from app.core.game_config import game_config
from app.schemas.common import RarityEnum
from app.schemas.dweller import DwellerTemplate
from app.utils.dwellers import create_dweller_from_template
from app.utils.places import GENERIC_ORIGIN_SKIP, normalize_place_name
from app.utils.static_data import game_data_store


def test_pick_template_exhaustion_returns_none() -> None:
    names = {f"{d.first_name} {d.last_name or ''}".strip() for d in game_data_store.get_dwellers_by_rarity("rare")}
    assert game_data_store.pick_template("rare", exclude_names=names) is None


def _template_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "first_name": "Test",
        "last_name": "Vault",
        "template_id": "test-vault",
        "gender": "Male",
        "rarity": "Rare",
        "strength": 5,
        "perception": 5,
        "endurance": 5,
        "charisma": 5,
        "intelligence": 5,
        "agility": 5,
        "luck": 5,
        "origin_place": "Rivet City",
        "visited_places": ["Megaton"],
        "bio": "Grew up in Rivet City.",
        "visual_attributes": {"race": "human", "faction": "vault_dweller"},
    }
    base.update(overrides)
    return base


def test_template_rejects_duplicate_normalized_visited() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        DwellerTemplate.model_validate(_template_payload(visited_places=["Megaton", "megaton"]))


def test_template_rejects_visited_matching_origin() -> None:
    with pytest.raises(ValueError, match="origin"):
        DwellerTemplate.model_validate(_template_payload(visited_places=["rivet city"]))


def test_template_rejects_blank_origin() -> None:
    with pytest.raises(ValueError, match="origin_place"):
        DwellerTemplate.model_validate(_template_payload(origin_place="   "))


def test_companion_template_allows_null_visuals() -> None:
    t = DwellerTemplate.model_validate(
        {
            "first_name": "CX404",
            "last_name": "",
            "template_id": "cx404",
            "gender": "Male",
            "rarity": "Legendary",
            "strength": 5,
            "perception": 7,
            "endurance": 7,
            "charisma": 6,
            "intelligence": 4,
            "agility": 9,
            "luck": 6,
            "origin_place": "Filly",
            "visited_places": [],
            "visual_attributes": None,
            "bio": "A loyal canine companion.",
        }
    )
    assert t.visual_attributes is None
    data = create_dweller_from_template(t)
    assert data["visual_attributes"] is None


def test_template_rejects_invalid_visual_identity() -> None:
    with pytest.raises(ValueError, match="not valid for race"):
        DwellerTemplate.model_validate(
            {
                "first_name": "Invalid",
                "last_name": "Identity",
                "template_id": "invalid-identity",
                "gender": "Male",
                "rarity": "Rare",
                "strength": 5,
                "perception": 5,
                "endurance": 5,
                "charisma": 5,
                "intelligence": 5,
                "agility": 5,
                "luck": 5,
                "origin_place": "Megaton",
                "visited_places": [],
                "visual_attributes": {"race": "human", "faction": "super_mutant_tribe"},
            }
        )

        # DwellerTemplate already validates race/faction combo via DwellerVisualAttributes
