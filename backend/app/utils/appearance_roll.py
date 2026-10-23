"""Semi-random, race-aware appearance rolls with parent inheritance.

Fills ``visual_attributes`` for any newly created/generated dweller and derives
newborn appearance from the parents, with a configurable trait-mutation chance.
Every emitted value stays inside the canonical per-race option lists
(``app.options.appearance``).

Deterministic: takes an injectable ``random.Random`` (or the ``random`` module)
like ``roll_child_identity``; no AI dependency. The AI visual-attributes agent
remains an optional enhancement and is never overwritten by these rolls.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from app.core.enums import ADULT_AGE_GROUPS, AgeGroupEnum, GenderEnum
from app.core.game_config import game_config
from app.options.appearance import (
    beard_options,
    body_type_options,
    eye_color_options,
    hair_color_options,
    haircuts,
    height_options,
    scalp_feature_descriptions,
    skin_tone_options,
)
from app.options.races import RaceOption

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

    from app.schemas.dweller_catalog import AppearancePools

# ---------------------------------------------------------------------------
# Default expression pool (used when no archetype pools are provided)
# ---------------------------------------------------------------------------

_DEFAULT_EXPRESSIONS: tuple[str, ...] = ("neutral", "stoic", "determined")

# Build display mapping: canonical build value -> prose adjective.
_BUILD_DISPLAY: dict[str, str] = {
    "Slim": "slim",
    "Athletic": "athletic",
    "Muscular": "muscular",
    "Stocky": "stocky",
    "Average": "average build",
    "Overweight": "heavyset",
    "Withered": "withered",
    "Skeletal": "skeletal",
    "Twisted": "twisted",
    "Brutish": "brutish",
    "Towering": "towering",
    "Slender": "slender",
    "Armored": "armored",
}


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
    values = [(parent.visual_attributes or {}).get(field) for parent in (mother, father)]
    valid = [value for value in values if value in options]
    return _mutate(rng, rng.choice(valid or options), options)


def _roll_with_pools(
    pool: Sequence[str] | None,
    canonical: Sequence[str],
    rng: random.Random | ModuleType,
) -> str:
    """Sample a constrained trait, falling back to its canonical options when omitted."""
    return rng.choice(canonical if pool is None else pool)


def roll_appearance(
    race: RaceOption,
    gender: GenderEnum | None,
    rng: random.Random | ModuleType = random,
    age_group: AgeGroupEnum = AgeGroupEnum.ADULT,
    appearance_pools: AppearancePools | None = None,
) -> dict[str, Any]:
    """Roll a complete, race-valid appearance profile for a new dweller.

    When ``appearance_pools`` (from a preset archetype entry) is provided,
    each listed trait is sampled from the corresponding pool rather than
    the full canonical list.  Unconstrained traits fall back to canonical.
    Facial hair is gender-gated.

    When no pools are given the behaviour is unchanged except that the
    expression picks from the small neutral-leaning default pool
    ``(_DEFAULT_EXPRESSIONS)`` rather than being hardcoded to ``"neutral"``.
    """
    pools: AppearancePools = appearance_pools or {}
    appearance: dict[str, Any] = {
        "race": race.value,
        "skin_tone": _roll_with_pools(pools.get("skin_tone"), skin_tone_options[race], rng),
        "hair_color": _roll_with_pools(pools.get("hair_color"), hair_color_options, rng),
        "eye_color": rng.choice(eye_color_options),
        "hair_style": _roll_with_pools(pools.get("hair_style"), haircuts[race], rng),
        "height": rng.choice(height_options),
        "build": _roll_with_pools(pools.get("build"), body_type_options[race], rng),
    }

    appearance["expression"] = _roll_with_pools(pools.get("expression"), _DEFAULT_EXPRESSIONS, rng)

    if gender == GenderEnum.MALE and age_group in ADULT_AGE_GROUPS:
        appearance["facial_hair"] = rng.choice(beard_options)
    else:
        appearance["facial_hair"] = "None"
    return appearance


def describe_appearance(appearance: dict[str, Any], gender: GenderEnum, race: RaceOption) -> str:
    """Build a single first-person appearance sentence.

    Example: ``"I'm a tall, stocky woman with ashen skin, stringy gray hair, and gray eyes."``

    Gender word: man/woman.  Facial hair is appended when present and not "None".
    Race-specific phrasing trails the sentence for non-humans (one variant each,
    deterministic).
    """
    gender_word = "woman" if gender == GenderEnum.FEMALE else "man"
    height_word = str(appearance.get("height", "average")).lower()
    build_word = _BUILD_DISPLAY.get(appearance.get("build", ""), "average build")
    skin = appearance.get("skin_tone", "")
    hair_style = appearance.get("hair_style", "")
    hair_color = appearance.get("hair_color", "")
    eye_color = appearance.get("eye_color", "")

    # Start the sentence.
    article = "an" if height_word.startswith(("a", "e", "i", "o", "u")) else "a"
    sentence = f"I'm {article} {height_word}, {build_word} {gender_word}"

    # Skin tone (plain here; race flavor trails the sentence).
    if skin and race == RaceOption.SYNTH:
        sentence += f" with {skin} synthetic skin"
    elif skin:
        sentence += f" with {skin} skin"
    else:
        sentence += f" with {gender_word.lower()}'s skin"

    # Hair. Styles like "Short Hair" or "Wavy Hair" already end in "hair" —
    # strip the suffix so we don't render "short hair blonde hair".
    # Bare scalps and exposed hardware never invent a hair color.
    style_word = hair_style.lower()
    if style_word.endswith("hair"):
        style_word = style_word.removesuffix("hair").strip()
    if scalp_feature := scalp_feature_descriptions.get(hair_style):
        sentence += f", {scalp_feature}"
    elif style_word and hair_color:
        sentence += f", {style_word} {hair_color} hair"
    elif style_word:
        sentence += f", {style_word} hair"
    elif hair_color:
        sentence += f", {hair_color} hair"

    # Eyes.
    sentence += f" and {eye_color} eyes"

    # Facial hair.
    facial_hair = appearance.get("facial_hair", "None")
    if facial_hair and facial_hair != "None":
        sentence += f", sporting a {facial_hair.lower()}"

    # Race flavor trails the sentence so the trait list stays readable.
    if race == RaceOption.GHOUL:
        sentence += " — my skin has been ash and scars since the bombs"
    elif race == RaceOption.SUPER_MUTANT:
        sentence += " — the vats do not apologize"
    elif race == RaceOption.SYNTH:
        sentence += " — assembled by hands I never met"

    return sentence + "."


def inherit_appearance_for_child(
    child_race: RaceOption,
    mother: Any,
    father: Any,
    rng: random.Random | ModuleType,
) -> dict[str, Any]:
    """Build the child's appearance: inherit from parents, race-correct for the child.

    Every inherited value is re-validated against the child's race options;
    values that cannot transfer (e.g. human skin tones onto a ghoul) re-roll
    cleanly.
    """
    appearance: dict[str, Any] = {
        "skin_tone": _inherit(rng, mother, father, "skin_tone", skin_tone_options, child_race),
        "hair_color": _inherit(rng, mother, father, "hair_color", hair_color_options, child_race),
        "eye_color": _inherit(rng, mother, father, "eye_color", eye_color_options, child_race),
        "hair_style": _inherit(rng, mother, father, "hair_style", haircuts, child_race),
        "height": _inherit(rng, mother, father, "height", height_options, child_race),
        "build": _inherit(rng, mother, father, "build", body_type_options, child_race),
    }
    appearance["facial_hair"] = "None"
    appearance["expression"] = "neutral"
    return appearance


def complete_appearance(data: dict[str, Any], rng: random.Random | ModuleType = random) -> dict[str, Any]:
    """Fill missing creation-time traits, preserving authored and AI values."""
    existing = {key: value for key, value in (data.get("visual_attributes") or {}).items() if value is not None}
    race = RaceOption(existing.get("race", RaceOption.HUMAN))
    rolled = roll_appearance(race, data.get("gender"), rng, data.get("age_group", AgeGroupEnum.ADULT))
    return rolled | existing
