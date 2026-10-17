"""Semi-random, race-aware appearance rolls with parent inheritance.

Fills ``visual_attributes`` for any newly created/generated dweller and derives
newborn appearance from the parents, with a configurable mutation chance.
Every emitted value stays inside the canonical per-race option lists
(``app.options.appearance``), including after a race mutation re-roll.

Deterministic: takes an injectable ``random.Random`` (or the ``random`` module)
like ``roll_child_identity``; no AI dependency. The AI visual-attributes agent
remains an optional enhancement and is never overwritten by these rolls.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from app.core.enums import GenderEnum
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

if TYPE_CHECKING:
    from types import ModuleType

#: Traits a child directly inherits from a parent (with mutation chance).
INHERITED_TRAITS: frozenset[str] = frozenset({"skin_tone", "hair_color", "eye_color", "hair_style"})


def _mutate(rng: random.Random | ModuleType, value: str, options: list[str]) -> str:
    """Pick a different valid option with ``trait_mutation_chance``, else keep."""
    if len(options) > 1 and rng.random() < game_config.breeding.trait_mutation_chance:
        return rng.choice([option for option in options if option != value])
    return value


def _inherit(
    rng: random.Random | ModuleType,
    mother: Any,
    father: Any,
    field: str,
    options_for_race: dict[RaceOption, list[str]] | list[str],
    child_race: RaceOption = RaceOption.HUMAN,
) -> str:
    """Inherit a single trait from a parent, race-validated for the child, with mutation."""
    if isinstance(options_for_race, dict):
        options = options_for_race.get(child_race) or options_for_race[RaceOption.HUMAN]
    else:
        options = options_for_race
    # Prefer a parent's stored value when it is valid for the child's race;
    # fall back to a race-valid roll when neither parent's value transfers
    # (e.g. human skin tones onto a ghoul child after a race mutation).
    for parent in (mother, father):
        value = (parent.visual_attributes or {}).get(field)
        if value in options:
            return _mutate(rng, value, options)
    return _mutate(rng, rng.choice(options), options)


def roll_appearance(
    race: RaceOption,
    gender: GenderEnum,
    rng: random.Random | ModuleType = random,
    age_group: Any = None,
) -> dict[str, Any]:
    """Roll a complete, race-valid appearance profile for a new dweller.

    Deterministic under a seeded ``rng``. Every value comes from the canonical
    option list for ``race``; facial hair is gender-gated. Equipment-derived
    fields (``accessory``, ``object_held``, ``headgear``) are left unset so
    youth never appear equipped (issue #1036 youth rule).
    """
    appearance: dict[str, Any] = {
        "race": race.value,
        "skin_tone": rng.choice(skin_tone_options[race]),
        "hair_color": rng.choice(hair_color_options),
        "eye_color": rng.choice(eye_color_options),
        "hair_style": rng.choice(haircuts[race]),
        "height": rng.choice(height_options),
        "build": rng.choice(body_type_options[race]),
        "expression": "neutral",
    }
    if gender == GenderEnum.MALE and (age_group is None or age_group != "child"):
        appearance["facial_hair"] = rng.choice(beard_options)
    else:
        appearance["facial_hair"] = "None"
    return appearance


def inherit_appearance_for_child(
    child_race: RaceOption,
    child_gender: GenderEnum,
    mother: Any,
    father: Any,
    rng: random.Random | ModuleType,
) -> dict[str, Any]:
    """Build the child's appearance: inherit from parents, race-correct for the child.

    The child's race may differ from both parents (race mutation), so every
    inherited value is re-validated against the child's race options; values
    that cannot transfer (e.g. human skin tones onto a ghoul) re-roll cleanly.
    """
    appearance: dict[str, Any] = {
        "skin_tone": _inherit(rng, mother, father, "skin_tone", skin_tone_options, child_race),
        "hair_color": _inherit(rng, mother, father, "hair_color", hair_color_options, child_race),
        "eye_color": _inherit(rng, mother, father, "eye_color", eye_color_options, child_race),
        "hair_style": _inherit(rng, mother, father, "hair_style", haircuts, child_race),
        "height": _inherit(rng, mother, father, "height", height_options, child_race),
        "build": _inherit(rng, mother, father, "build", body_type_options, child_race),
    }
    if child_gender == GenderEnum.MALE:
        appearance["facial_hair"] = _inherit(rng, mother, father, "facial_hair", beard_options)
    else:
        appearance["facial_hair"] = "None"
    appearance["expression"] = "neutral"
    return appearance
