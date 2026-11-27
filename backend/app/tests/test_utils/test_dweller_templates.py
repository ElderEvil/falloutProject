import pytest

from app.schemas.dweller import DwellerTemplate
from app.utils.dweller_generation import create_dweller_from_template
from app.utils.static_data import game_data_store

PAYLOAD = {
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


def test_pick_template_exhaustion_returns_none() -> None:
    names = {f"{d.first_name} {d.last_name or ''}".strip() for d in game_data_store.get_dwellers_by_rarity("rare")}
    assert game_data_store.pick_template("rare", exclude_names=names) is None


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"visited_places": ["Megaton", "megaton"]}, "duplicate"),
        ({"visited_places": ["rivet city"]}, "origin"),
        ({"origin_place": "   "}, "origin_place"),
        ({"visual_attributes": {"race": "human", "faction": "super_mutant_tribe"}}, "not valid for race"),
    ],
)
def test_template_rejects_invalid_payload(overrides: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        DwellerTemplate.model_validate(PAYLOAD | overrides)


def test_companion_template_allows_null_visuals_and_generates_defaults() -> None:
    template = DwellerTemplate.model_validate(
        PAYLOAD
        | {
            "first_name": "Snip Snip",
            "last_name": "",
            "template_id": "snip-snip",
            "rarity": "Legendary",
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
    assert template.visual_attributes is None
    data = create_dweller_from_template(template)
    assert data["visual_attributes"]["race"] == "human"
    assert data["visual_attributes"]["hair_style"]
