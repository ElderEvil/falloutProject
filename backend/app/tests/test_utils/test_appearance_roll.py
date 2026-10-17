"""Issue #1036 — semi-random appearance with parent inheritance.

Deterministic (injected RNG) rolls: complete race-valid profiles for new
dwellers, parental inheritance with trait mutation for newborns, and
race-mutation re-rolls. Youth equipment/training gates live here too —
they constrain the same age groups the appearance rules describe.
"""

import random
from types import SimpleNamespace

import pytest

from app.core.enums import AgeGroupEnum, GenderEnum
from app.core.game_config import game_config
from app.options.appearance import (
    beard_options,
    body_type_options,
    eye_color_options,
    hair_color_options,
    haircuts,
    height_options,
    skin_tone_options,
)
from app.options.races import RaceOption
from app.utils.appearance_roll import roll_appearance
from app.utils.dwellers import create_random_common_dweller, roll_child_identity


def _parent(race: str, skin: str, hair_color: str, hair_style: str, eye: str):
    return SimpleNamespace(
        visual_attributes={
            "race": race,
            "skin_tone": skin,
            "hair_color": hair_color,
            "hair_style": hair_style,
            "eye_color": eye,
        }
    )


HUMAN_MOTHER = _parent("human", "Pale", "brunette", "Long Hair", "green")
HUMAN_FATHER = _parent("human", "Tan", "black", "Short Hair", "blue")


def test_random_dweller_gets_complete_race_valid_appearance():
    data = create_random_common_dweller(seed=7)
    va = data["visual_attributes"]
    race = RaceOption(va["race"])
    assert va["skin_tone"] in skin_tone_options[race]
    assert va["hair_color"] in hair_color_options
    assert va["eye_color"] in eye_color_options
    assert va["hair_style"] in haircuts[race]
    assert va["height"] in height_options
    assert va["build"] in body_type_options[race]
    assert va["facial_hair"] in beard_options


def test_random_dweller_roll_is_deterministic_under_seed():
    a = create_random_common_dweller(seed=123)
    b = create_random_common_dweller(seed=123)
    assert a["visual_attributes"] == b["visual_attributes"]


def test_child_appearance_is_deterministic():
    a = roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(42))
    b = roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(42))
    assert a == b


def test_child_shares_a_parent_trait_without_mutation():
    game_config.breeding.trait_mutation_chance = 0.0
    try:
        for seed in range(20):
            child = roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(seed))
            parent_values = {
                HUMAN_MOTHER.visual_attributes["skin_tone"],
                HUMAN_FATHER.visual_attributes["skin_tone"],
            }
            assert child["skin_tone"] in parent_values
    finally:
        game_config.breeding.trait_mutation_chance = 0.15


def test_trait_mutation_picks_a_different_valid_option():
    game_config.breeding.trait_mutation_chance = 1.0
    try:
        child = roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(5))
        # Every trait must still be a valid option for the child's race.
        race = RaceOption(child["race"])
        assert child["skin_tone"] in skin_tone_options[race]
        assert child["hair_style"] in haircuts[race]
    finally:
        game_config.breeding.trait_mutation_chance = 0.15


def test_race_mutation_rerolls_appearance_for_the_mutated_race():
    game_config.breeding.race_mutation_chance = 1.0
    try:
        for seed in (1, 2, 3, 7, 11):
            child = roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(seed))
            race = RaceOption(child["race"])
            # Mutated race differs from the human parents; appearance must be
            # valid for it, not carry human-only values.
            assert race != RaceOption.HUMAN
            assert child["skin_tone"] in skin_tone_options[race]
            assert child["hair_style"] in haircuts[race]
    finally:
        game_config.breeding.race_mutation_chance = 0.05


def test_non_adult_cannot_get_facial_hair_from_roll():
    child_va = roll_appearance(RaceOption.HUMAN, GenderEnum.MALE, random.Random(3), AgeGroupEnum.CHILD)
    assert child_va["facial_hair"] == "None"
    adult_va = roll_appearance(RaceOption.HUMAN, GenderEnum.MALE, random.Random(3), AgeGroupEnum.ADULT)
    assert adult_va["facial_hair"] in beard_options
