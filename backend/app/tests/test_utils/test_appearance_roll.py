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
from app.schemas.dweller import DwellerCreate
from app.services.dweller_service import dweller_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.utils.appearance_roll import describe_appearance, roll_appearance
from app.utils.dweller_generation import create_dweller_from_template, create_random_common_dweller
from app.utils.dwellers import roll_child_identity
from app.utils.static_data import game_data_store


def _parent(race: str, skin: str, hair_color: str, hair_style: str, eye: str):
    attrs = {"race": race, "skin_tone": skin, "hair_color": hair_color, "hair_style": hair_style, "eye_color": eye}
    return SimpleNamespace(visual_attributes=attrs)


HUMAN_MOTHER = _parent("human", "Pale", "brunette", "Long Hair", "green")
HUMAN_FATHER = _parent("human", "Tan", "black", "Short Hair", "blue")


def test_random_dweller_gets_complete_race_valid_appearance():
    va = create_random_common_dweller(seed=7)["visual_attributes"]
    race = RaceOption(va["race"])
    assert va["skin_tone"] in skin_tone_options[race]
    assert va["hair_color"] in hair_color_options
    assert va["eye_color"] in eye_color_options
    assert va["hair_style"] in haircuts[race]
    assert va["height"] in height_options
    assert va["build"] in body_type_options[race]
    assert va["facial_hair"] in beard_options


def test_rolls_are_deterministic_under_seed():
    first, second = create_random_common_dweller(seed=123), create_random_common_dweller(seed=123)
    assert first["visual_attributes"] == second["visual_attributes"]
    assert roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(42)) == roll_child_identity(
        HUMAN_MOTHER, HUMAN_FATHER, random.Random(42)
    )
    template = game_data_store.get_dweller("snip-snip")
    assert (
        create_dweller_from_template(template, seed=7)["visual_attributes"]
        == create_dweller_from_template(template, seed=7)["visual_attributes"]
    )
    assert (
        create_dweller_from_template(template, seed=7)["visual_attributes"]["hair_style"] in haircuts[RaceOption.HUMAN]
    )


def test_children_inherit_both_parents_without_mutation(monkeypatch):
    monkeypatch.setattr(game_config.breeding, "trait_mutation_chance", 0.0)
    parent_skin = {HUMAN_MOTHER.visual_attributes["skin_tone"], HUMAN_FATHER.visual_attributes["skin_tone"]}
    for seed in range(20):
        assert roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(seed))["skin_tone"] in parent_skin
    children = [roll_child_identity(HUMAN_MOTHER, HUMAN_FATHER, random.Random(seed)) for seed in range(40)]
    assert {child["skin_tone"] for child in children} == {"Pale", "Tan"}
    assert {child["eye_color"] for child in children} == {"green", "blue"}
    for child in children:
        assert child["facial_hair"] == "None"
        assert "gender" not in child
    monkeypatch.setattr(game_config.breeding, "trait_mutation_chance", 1.0)
    mother = _parent("human", "Pale", "brunette", "Long Hair", "green")
    father = _parent("human", "Pale", "black", "Short Hair", "blue")
    child = roll_child_identity(mother, father, random.Random(5))
    race = RaceOption(child["race"])
    assert child["skin_tone"] in skin_tone_options[race]
    assert child["hair_style"] in haircuts[race]
    assert child["skin_tone"] != "Pale"


def test_non_adult_cannot_get_facial_hair_from_roll():
    for age_group in (AgeGroupEnum.CHILD, AgeGroupEnum.TEEN):
        for seed in range(10):
            appearance = roll_appearance(RaceOption.HUMAN, GenderEnum.MALE, random.Random(seed), age_group)
            assert appearance["facial_hair"] == "None"
    adult_va = roll_appearance(RaceOption.HUMAN, GenderEnum.MALE, random.Random(3), AgeGroupEnum.ADULT)
    assert adult_va["facial_hair"] in beard_options


@pytest.mark.asyncio
async def test_generic_creation_fills_only_missing_traits(async_session, vault):
    attrs = {"race": "human", "hair_color": "authored silver", "expression": "smiling"}
    payload = DwellerCreate(**(create_fake_adult_dweller() | {"vault_id": vault.id, "visual_attributes": attrs}))
    created = await dweller_service.create_dweller(async_session, payload)
    assert created is not None
    assert created.visual_attributes is not None
    assert created.visual_attributes.items() >= attrs.items()
    assert created.visual_attributes["skin_tone"] in skin_tone_options[RaceOption.HUMAN]


@pytest.mark.parametrize(("height", "expected"), [("Tall", "a tall"), ("Average", "an average"), ("SHORT", "a short")])
@pytest.mark.parametrize(("gender", "word"), [(GenderEnum.FEMALE, "woman"), (GenderEnum.MALE, "man")])
def test_describe_appearance_normalizes_height_and_article(height, expected, gender, word):
    appearance = roll_appearance(RaceOption.HUMAN, gender, random.Random(7))
    appearance.update(height=height, build="Slim")
    assert describe_appearance(appearance, gender, RaceOption.HUMAN).startswith(f"I'm {expected}, slim {word} with ")


@pytest.mark.parametrize(
    ("race", "style", "clause"),
    [
        (RaceOption.SUPER_MUTANT, "Bald", "a bald scalp"),
        (RaceOption.SUPER_MUTANT, "Scalp Ridges", "scalp ridges"),
        (RaceOption.SUPER_MUTANT, "War Paint Scalp", "war paint on my scalp"),
        (RaceOption.GHOUL, "Burned Scalp", "a burned scalp"),
        (RaceOption.GHOUL, "Radiation-Scarred", "a radiation-scarred scalp"),
        (RaceOption.SYNTH, "Exposed Circuits", "exposed circuits on my scalp"),
    ],
)
def test_describe_scalp_features_without_inventing_hair(race, style, clause):
    appearance = roll_appearance(race, GenderEnum.FEMALE, random.Random(7))
    appearance.update(hair_style=style, hair_color="pink")
    description = describe_appearance(appearance, GenderEnum.FEMALE, race)
    assert clause in description
    assert "pink" not in description
    assert "hair" not in description
