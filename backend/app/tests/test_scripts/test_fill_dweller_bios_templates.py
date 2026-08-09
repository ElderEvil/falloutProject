"""Tests for the template-based dweller bio filler script."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.models.dweller import Dweller
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum, GenderEnum, RarityEnum
from scripts.fill_dweller_bios_templates import _build_bio, _highest_stat, _join_places, _pick_places


def _make_dweller(**overrides: object) -> Dweller:
    defaults = {
        "id": uuid4(),
        "first_name": "Test",
        "last_name": "Dweller",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "status": DwellerStatusEnum.IDLE,
        "level": 1,
        "strength": 1,
        "perception": 1,
        "endurance": 1,
        "charisma": 1,
        "intelligence": 1,
        "agility": 1,
        "luck": 1,
    }
    defaults.update(overrides)
    return Dweller(**defaults)


def test_highest_stat_picks_single_max():
    dweller = _make_dweller(strength=3, perception=1, endurance=5, charisma=2)
    assert _highest_stat(dweller) == "endurance"


def test_highest_stat_tie_breaks_to_one_of_top():
    dweller = _make_dweller(strength=5, perception=5, endurance=1, charisma=1)
    assert _highest_stat(dweller) in {"strength", "perception"}


def test_pick_places_is_deterministic_per_dweller_id():
    dweller = _make_dweller(id=UUID("12345678-1234-5678-1234-567812345678"))
    origin1, visited1 = _pick_places(dweller)
    origin2, visited2 = _pick_places(dweller)
    assert origin1 == origin2
    assert visited1 == visited2


def test_pick_places_origin_and_visited_are_distinct():
    dweller = _make_dweller(id=UUID("12345678-1234-5678-1234-567812345678"))
    origin, visited = _pick_places(dweller)
    assert origin not in visited


def test_pick_places_common_rarity_gets_two_visited():
    dweller = _make_dweller(rarity=RarityEnum.COMMON)
    _origin, visited = _pick_places(dweller)
    assert len(visited) == 2


def test_pick_places_rare_rarity_gets_four_visited():
    dweller = _make_dweller(rarity=RarityEnum.RARE)
    _origin, visited = _pick_places(dweller)
    assert len(visited) == 4


def test_pick_places_legendary_rarity_gets_five_visited():
    dweller = _make_dweller(rarity=RarityEnum.LEGENDARY)
    _origin, visited = _pick_places(dweller)
    assert len(visited) == 5


def test_build_bio_includes_origin_and_visited():
    dweller = _make_dweller(
        first_name="Ada",
        last_name="Lovelace",
        strength=5,
        perception=1,
        endurance=1,
        charisma=1,
        intelligence=1,
        agility=1,
        luck=1,
    )
    bio = _build_bio(dweller, origin="Megaton", visited=["the Pitt"])
    assert "Ada Lovelace" in bio
    assert "Megaton" in bio
    assert "the Pitt" in bio
    assert "Strength" in bio
    assert "5" in bio


def test_build_bio_with_two_visited_places_joins_with_and():
    dweller = _make_dweller(
        first_name="Ada",
        strength=5,
    )
    bio = _build_bio(dweller, origin="Megaton", visited=["the Pitt", "Far Harbor"])
    assert "the Pitt and Far Harbor" in bio


def test_join_places_one():
    assert _join_places(["Megaton"]) == "Megaton"


def test_join_places_two():
    assert _join_places(["the Pitt", "Far Harbor"]) == "the Pitt and Far Harbor"


def test_join_places_three_uses_oxford_comma():
    assert _join_places(["A", "B", "C"]) == "A, B, and C"


def test_join_places_five_uses_oxford_comma():
    places = ["the Capital Wasteland", "Mojave", "Glowing Sea", "the Commonwealth", "Appalachia"]
    result = _join_places(places)
    assert result == "the Capital Wasteland, Mojave, Glowing Sea, the Commonwealth, and Appalachia"


def test_build_bio_fits_max_length():
    dweller = _make_dweller(
        first_name="Christopher",
        last_name="Maximilian",
        strength=10,
        perception=10,
        endurance=10,
        charisma=10,
        intelligence=10,
        agility=10,
        luck=10,
    )
    bio = _build_bio(dweller, origin="Sanctuary Hills", visited=["the Capital Wasteland", "the Mojave desert"])
    assert len(bio) <= 1024


@pytest.mark.parametrize(
    ("stat", "value"),
    [
        ("strength", 7),
        ("perception", 7),
        ("endurance", 7),
        ("charisma", 7),
        ("intelligence", 7),
        ("agility", 7),
        ("luck", 7),
    ],
)
def test_build_bio_for_every_stat_branch(stat: str, value: int):
    dweller = _make_dweller(**{stat: value})
    bio = _build_bio(dweller, origin="Vault 101", visited=["Rivet City"])
    assert bio
    assert "Vault 101" in bio
    assert "Rivet City" in bio
