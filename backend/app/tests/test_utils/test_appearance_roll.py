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
from app.utils.appearance_roll import describe_appearance, roll_appearance
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


def test_child_shares_a_parent_trait_without_mutation(monkeypatch):
    monkeypatch.setattr(game_config.breeding, "trait_mutation_chance", 0.0)
    monkeypatch.setattr(game_config.breeding, "race_mutation_chance", 0.0)
    for seed in range(20):
        child = roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(seed))
        parent_values = {
            HUMAN_MOTHER.visual_attributes["skin_tone"],
            HUMAN_FATHER.visual_attributes["skin_tone"],
        }
        assert child["skin_tone"] in parent_values


def test_trait_mutation_picks_a_different_valid_option(monkeypatch):
    monkeypatch.setattr(game_config.breeding, "trait_mutation_chance", 1.0)
    monkeypatch.setattr(game_config.breeding, "race_mutation_chance", 0.0)
    mother = _parent("human", "Pale", "brunette", "Long Hair", "green")
    father = _parent("human", "Pale", "black", "Short Hair", "blue")
    child = roll_child_identity(mother, father, random.Random(5))
    race = RaceOption(child["race"])
    assert child["skin_tone"] in skin_tone_options[race]
    assert child["hair_style"] in haircuts[race]
    assert child["skin_tone"] != "Pale"


def test_race_mutation_rerolls_appearance_for_the_mutated_race(monkeypatch):
    monkeypatch.setattr(game_config.breeding, "race_mutation_chance", 1.0)
    for seed in (1, 2, 3, 7, 11):
        child = roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(seed))
        race = RaceOption(child["race"])
        assert race != RaceOption.HUMAN
        assert child["skin_tone"] in skin_tone_options[race]
        assert child["hair_style"] in haircuts[race]


def test_non_adult_cannot_get_facial_hair_from_roll():
    child_va = roll_appearance(RaceOption.HUMAN, GenderEnum.MALE, random.Random(3), AgeGroupEnum.CHILD)
    assert child_va["facial_hair"] == "None"
    adult_va = roll_appearance(RaceOption.HUMAN, GenderEnum.MALE, random.Random(3), AgeGroupEnum.ADULT)
    assert adult_va["facial_hair"] in beard_options


def test_both_parents_contribute_traits(monkeypatch):
    monkeypatch.setattr(game_config.breeding, "trait_mutation_chance", 0.0)
    monkeypatch.setattr(game_config.breeding, "race_mutation_chance", 0.0)
    children = [roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(seed)) for seed in range(40)]
    assert {child["skin_tone"] for child in children} == {"Pale", "Tan"}
    assert {child["eye_color"] for child in children} == {"green", "blue"}


def test_newborn_appearance_has_no_beard_or_separate_gender():
    for seed in range(40):
        child = roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(seed))
        assert child["facial_hair"] == "None"
        assert "gender" not in child


@pytest.mark.parametrize("age_group", [AgeGroupEnum.CHILD, AgeGroupEnum.TEEN])
def test_all_youth_rolls_have_no_beard(age_group):
    for seed in range(10):
        assert (
            roll_appearance(RaceOption.HUMAN, GenderEnum.MALE, random.Random(seed), age_group)["facial_hair"] == "None"
        )


def test_template_without_visuals_gets_seeded_profile():
    from app.utils.dwellers import create_dweller_from_template
    from app.utils.static_data import game_data_store

    template = game_data_store.get_dweller("snip-snip")
    first = create_dweller_from_template(template, seed=7)
    second = create_dweller_from_template(template, seed=7)
    assert first["visual_attributes"]
    assert first["visual_attributes"] == second["visual_attributes"]
    assert first["visual_attributes"]["hair_style"] in haircuts[RaceOption.HUMAN]


@pytest.mark.asyncio
async def test_generic_creation_fills_only_missing_traits(async_session, vault):
    from app.schemas.dweller import DwellerCreate
    from app.services.dweller_service import dweller_service
    from app.tests.factory.dwellers import create_fake_adult_dweller

    attrs = {"race": "human", "hair_color": "authored silver", "expression": "smiling"}
    payload = DwellerCreate(**(create_fake_adult_dweller() | {"vault_id": vault.id, "visual_attributes": attrs}))
    created = await dweller_service.create_dweller(async_session, payload)
    assert created.visual_attributes.items() >= attrs.items()
    assert created.visual_attributes["skin_tone"] in skin_tone_options[RaceOption.HUMAN]


@pytest.mark.parametrize(
    ("height", "expected"),
    [("Tall", "a tall"), ("Average", "an average"), ("SHORT", "a short")],
)
@pytest.mark.parametrize(("gender", "word"), [(GenderEnum.FEMALE, "woman"), (GenderEnum.MALE, "man")])
def test_describe_appearance_normalizes_height_and_article(height, expected, gender, word):
    appearance = roll_appearance(RaceOption.HUMAN, gender, random.Random(7))
    appearance.update(height=height, build="Slim")
    description = describe_appearance(appearance, gender, RaceOption.HUMAN)
    assert description.startswith(f"I'm {expected}, slim {word} with ")
