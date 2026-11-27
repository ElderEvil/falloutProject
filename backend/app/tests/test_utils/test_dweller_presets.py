import ast
import inspect
import random

import pytest

from app.core.enums import AgeGroupEnum, GenderEnum
from app.core.game_config import game_config
from app.options import bios, presets
from app.options.appearance import (
    body_type_options,
    expression_options,
    hair_color_options,
    haircuts,
    skin_tone_options,
)
from app.options.bios import ZONE_RUMORS
from app.options.presets import archetypes
from app.options.races import RaceOption
from app.utils.appearance_roll import describe_appearance, roll_appearance
from app.utils.dweller_generation import create_random_common_dweller

POOL_SOURCES = {
    "skin_tone": lambda race: skin_tone_options.get(race, []),
    "hair_color": lambda race: hair_color_options,
    "hair_style": lambda race: haircuts.get(race, []),
    "build": lambda race: body_type_options.get(race, []),
    "expression": lambda race: expression_options,
}


def _pools():
    for name, entry in archetypes.items():
        pools = entry.get("appearance_pools")
        if pools is not None:
            yield name, entry.get("race") or RaceOption.HUMAN, pools


def test_presets_importable_with_core_entries():
    assert len(archetypes) >= 5
    assert "Vault Dweller" in archetypes
    assert "Super Mutant Brute" in archetypes


def test_every_pool_subset_of_canonical():
    for name, race, pools in _pools():
        for key, canonical in POOL_SOURCES.items():
            for value in pools.get(key) or ():
                assert value in canonical(race), f"{name}: {key} {value!r} not canonical for {race}"


def test_archetype_pools_constrain_to_pool_values():
    for name, race, pools in _pools():
        for seed in range(10):
            rolled = roll_appearance(
                race, GenderEnum.MALE, random.Random(seed), AgeGroupEnum.ADULT, appearance_pools=pools
            )
            for key in POOL_SOURCES:
                values = pools.get(key)
                if values:
                    assert rolled[key] in values, f"{name}: {key} {rolled[key]!r} not in pool"
    counts: dict[RaceOption, int] = dict.fromkeys(RaceOption, 0)
    for entry in archetypes.values():
        race = entry.get("race")
        if race and race in counts:
            counts[race] += 1
    for race, count in counts.items():
        assert count >= 2, f"Race {race.value} has only {count} archetypes (need >=2)"


def test_weights_and_personality_lines():
    for name, entry in archetypes.items():
        weight = entry.get("weight", 0)
        assert weight > 0, f"{name}: weight {weight} must be positive"
    for name, entry in archetypes.items():
        lines = entry.get("personality_lines", ())
        assert lines, f"{name}: personality_lines must be non-empty"
        for line in lines:
            assert line.startswith("I "), f"{name}: personality line does not start with 'I ': {line!r}"
            assert len(line) > 0, f"{name}: empty personality line"
    for catalog in (bios, presets):
        tree = ast.parse(inspect.getsource(catalog))
        definitions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        assert not definitions, f"{catalog.__name__} contains behavior: {definitions}"


@pytest.mark.parametrize("race", list(RaceOption))
def test_generated_bio_matches_identity_and_keeps_rumor_last(monkeypatch, race):
    monkeypatch.setattr(
        game_config.dweller, "race_weights", {option.value: int(option == race) for option in RaceOption}
    )
    monkeypatch.setattr(game_config.bio, "zone_rumor_chance", 1.0)
    for seed in range(5):
        dweller = create_random_common_dweller(seed=seed)
        assert dweller == create_random_common_dweller(seed=seed)
        appearance = dweller["visual_attributes"]
        assert appearance["race"] == race.value
        assert describe_appearance(appearance, dweller["gender"], race) in dweller["bio"]
        personalities = (
            line for entry in archetypes.values() if entry["race"] == race for line in entry["personality_lines"]
        )
        assert any(line in dweller["bio"] for line in personalities)
        assert dweller["bio"].endswith(ZONE_RUMORS)
