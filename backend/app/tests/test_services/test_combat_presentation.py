"""Presentation snapshots use actual catalog equipment and race without changing skills."""

import pytest

from app.models.dweller import Dweller
from app.services.catalog_service import load_outfits, load_weapons
from app.services.combat.weapon_skill import attack_effect, combat_body, weapon_skill
from app.utils.item_factory import build_outfit, build_weapon


@pytest.mark.parametrize(
    ("race", "state", "expected"),
    [
        ("human", None, "human"),
        (None, None, "human"),
        ("unknown", None, "human"),
        ("ghoul", "sane", "ghoul"),
        ("ghoul", "wild", "feral"),
        ("ghoul", "feral", "feral"),
        ("super_mutant", "mild", "mutant"),
        ("super_mutant", "average", "mutant"),
        ("super_mutant", "behemoth", "behemoth"),
        ("synth", "gen_1", "synth"),
        ("synth", "gen_2", "synth"),
        ("synth", "gen_3", "human"),
        ("synth", None, "human"),
        ("synth", "unknown", "human"),
    ],
)
def test_body_profiles_follow_identity_and_only_power_armor_overrides(race, state, expected):
    dweller = Dweller(visual_attributes={"race": race, "state_of_being": state})
    assert combat_body(dweller) == expected
    for data in load_outfits():
        dweller.outfit = build_outfit(data, data["rarity"])
        assert combat_body(dweller) == ("power-armor" if data["outfit_type"] == "power_armor" else expected)


def test_catalog_delivery_and_family_exceptions_preserve_skill_selection():
    expected = {
        "Power fist": "punch",
        "Pool cue": "thrust",
        "Plasma rifle": "pulse",
        "Gatling laser": "beam",
        "Ultracite Gatling laser": "beam",
        "Junk Jet": "debris",
        "Laser rifle": "beam",
        "10mm pistol": "shot",
        "Flamer": "flame",
        "Fat Man": "blast",
    }
    seen = set()
    for data in load_weapons():
        dweller = Dweller()
        dweller.weapon = build_weapon(data, data["rarity"])
        skill = weapon_skill(dweller)
        assert attack_effect(dweller)
        assert attack_effect(dweller, skill)
        assert weapon_skill(dweller) == skill
        if data["name"] in expected:
            assert attack_effect(dweller) == expected[data["name"]]
            seen.add(data["name"])
    assert seen == set(expected)
    assert attack_effect(Dweller()) == "punch"
