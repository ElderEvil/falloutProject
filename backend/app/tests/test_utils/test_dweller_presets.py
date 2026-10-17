"""Extended presets validation.

Checks that ``app.options.presets.archetypes`` entries have appearance pools
that are subsets of the canonical lists, every race has at least two entries,
weights are positive, and all personality lines start with "I " (first-person).
"""

import random

from app.core.enums import AgeGroupEnum, GenderEnum
from app.options.appearance import (
    body_type_options,
    expression_options,
    hair_color_options,
    haircuts,
    skin_tone_options,
)
from app.options.presets import archetypes
from app.options.races import RaceOption
from app.utils.appearance_roll import roll_appearance


def test_presets_importable_with_core_entries():
    """Archetype presets should be importable with core archetypes."""
    assert len(archetypes) >= 5
    assert "Vault Dweller" in archetypes
    assert "Super Mutant Brute" in archetypes


def test_every_pool_subset_of_canonical():
    """Every appearance_pool value must exist in the canonical lists."""
    for name, entry in archetypes.items():
        pools = entry.get("appearance_pools")
        if pools is None:
            continue
        race = entry.get("race") or RaceOption.HUMAN

        # skin_tone
        if pools.get("skin_tone"):
            opts = skin_tone_options.get(race, [])
            for v in pools["skin_tone"]:
                assert v in opts, f"{name}: skin_tone {v!r} not in canonical list for {race}"

        # hair_color (None means unconstrained — skip; explicit list must be subset)
        if pools.get("hair_color") is not None:
            for v in pools["hair_color"]:
                assert v in hair_color_options, f"{name}: hair_color {v!r} not in canonical list"

        # hair_style
        if pools.get("hair_style"):
            opts = haircuts.get(race, [])
            for v in pools["hair_style"]:
                assert v in opts, f"{name}: hair_style {v!r} not in canonical list for {race}"

        # build
        if pools.get("build"):
            opts = body_type_options.get(race, [])
            for v in pools["build"]:
                assert v in opts, f"{name}: build {v!r} not in canonical list for {race}"

        # expression
        if pools.get("expression"):
            for v in pools["expression"]:
                assert v in expression_options, f"{name}: expression {v!r} not in canonical expression keys"


def test_every_race_has_at_least_two_entries():
    """Each race should have at least two archetype options."""
    counts: dict[RaceOption, int] = dict.fromkeys(RaceOption, 0)
    for entry in archetypes.values():
        race = entry.get("race")
        if race and race in counts:
            counts[race] += 1
    for race, count in counts.items():
        assert count >= 2, f"Race {race.value} has only {count} archetypes (need >=2)"


def test_all_weights_positive():
    """Every archetype entry with a weight must have weight > 0."""
    for name, entry in archetypes.items():
        weight = entry.get("weight", 0)
        assert weight > 0, f"{name}: weight {weight} must be positive"


def test_personality_lines_non_empty_and_first_person():
    """Every personality_line must be non-empty and start with 'I '."""
    for name, entry in archetypes.items():
        lines = entry.get("personality_lines", ())
        assert lines, f"{name}: personality_lines must be non-empty"
        for line in lines:
            assert line.startswith("I "), f"{name}: personality line does not start with 'I ': {line!r}"
            assert len(line) > 0, f"{name}: empty personality line"


def test_archetype_pools_constrain_to_pool_values():
    """When appearance_pools are provided, rolls must stay within the pool values."""
    for name, entry in archetypes.items():
        pools = entry.get("appearance_pools")
        if pools is None:
            continue
        race = entry.get("race") or RaceOption.HUMAN

        for seed in range(10):
            rolled = roll_appearance(
                race,
                GenderEnum.MALE,
                random.Random(seed),
                AgeGroupEnum.ADULT,
                appearance_pools=pools,
            )
            # Check constrained traits stay in pool
            if pools.get("skin_tone"):
                assert rolled["skin_tone"] in pools["skin_tone"], (
                    f"{name}: skin_tone {rolled['skin_tone']!r} not in pool"
                )
            if pools.get("hair_color") is not None:
                assert rolled["hair_color"] in pools["hair_color"], (
                    f"{name}: hair_color {rolled['hair_color']!r} not in pool"
                )
            if pools.get("hair_style"):
                assert rolled["hair_style"] in pools["hair_style"], (
                    f"{name}: hair_style {rolled['hair_style']!r} not in pool"
                )
            if pools.get("build"):
                assert rolled["build"] in pools["build"], f"{name}: build {rolled['build']!r} not in pool"
            if pools.get("expression"):
                assert rolled["expression"] in pools["expression"], (
                    f"{name}: expression {rolled['expression']!r} not in pool"
                )
