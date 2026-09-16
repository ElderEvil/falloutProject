"""Race and state-of-being enums with lore descriptions."""

from dataclasses import dataclass
from enum import StrEnum


class RaceOption(StrEnum):
    """Playable/non-playable race options for character appearance."""

    HUMAN = "human"
    GHOUL = "ghoul"
    SUPER_MUTANT = "super_mutant"
    SYNTH = "synth"


class GenderOption(StrEnum):
    """Gender options for character generation."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class GhoulFeralness(StrEnum):
    """State of being for Ghoul characters."""

    SANE = "sane"
    WILD = "wild"
    FERAL = "feral"


class SuperMutantMutation(StrEnum):
    """State of being for Super Mutant characters."""

    MILD = "mild"
    AVERAGE = "average"
    BEHEMOTH = "behemoth"


class SynthType(StrEnum):
    """State of being for Synth characters."""

    GEN_3 = "gen_3"
    GEN_2 = "gen_2"
    GEN_1 = "gen_1"


# Union type for state_of_being field
STATE_OF_BEING_OPTIONS: dict[RaceOption, list[StrEnum]] = {
    RaceOption.GHOUL: list(GhoulFeralness),
    RaceOption.SUPER_MUTANT: list(SuperMutantMutation),
    RaceOption.SYNTH: list(SynthType),
}

STATE_OF_BEING_VALUES: dict[RaceOption, list[str]] = {
    race: [s.value for s in states] for race, states in STATE_OF_BEING_OPTIONS.items()
}

#: Whether a race can conceive. Non-humans do not give birth; they enter the
#: population through recruitment, seeding, recycling, and breeding mutation.
BREEDING_ELIGIBLE: dict[RaceOption, bool] = {
    RaceOption.HUMAN: True,
    RaceOption.GHOUL: False,
    RaceOption.SUPER_MUTANT: False,
    RaceOption.SYNTH: False,
}


@dataclass(frozen=True)
class RaceModifiers:
    """Racial stat deltas and passive perks, declared beside the race options.

    Deltas are applied at the stat level (see ``options/identity_modifiers.py``), so
    combat, production and radiation all read one rule instead of branching per system.
    Values are deliberately small; a balance pass follows play-testing.
    """

    strength: int = 0
    perception: int = 0
    endurance: int = 0
    charisma: int = 0
    intelligence: int = 0
    agility: int = 0
    luck: int = 0
    radiation_immune: bool = False
    radiation_resist_pct: float = 0.0


#: Racial modifiers keyed by race; humans are the baseline every other race trades against.
RACE_MODIFIERS: dict[RaceOption, RaceModifiers] = {
    RaceOption.HUMAN: RaceModifiers(),
    RaceOption.GHOUL: RaceModifiers(endurance=2, radiation_immune=True),
    RaceOption.SUPER_MUTANT: RaceModifiers(strength=3, endurance=2, perception=-2),
    RaceOption.SYNTH: RaceModifiers(perception=1, intelligence=1, radiation_resist_pct=0.5),
}


def modifiers_for_race(entity: object) -> RaceModifiers:
    """Racial modifiers for an entity; unknown or missing races take the human baseline."""
    return RACE_MODIFIERS.get(race_of(entity) or RaceOption.HUMAN, RACE_MODIFIERS[RaceOption.HUMAN])


def race_of(entity: object) -> RaceOption | None:
    """Read an entity's race from its ``visual_attributes`` JSONB, if present and valid."""
    attrs = getattr(entity, "visual_attributes", None)
    raw = attrs.get("race") if isinstance(attrs, dict) else None
    if raw is None:
        return None
    try:
        return RaceOption(raw)
    except ValueError:
        return None


def can_breed(entity: object) -> bool:
    """Whether an entity's race may conceive; entities without a race default to human."""
    return BREEDING_ELIGIBLE.get(race_of(entity) or RaceOption.HUMAN, False)


race_descriptions: dict[RaceOption, str] = {
    RaceOption.GHOUL: (
        "A Ghoul is a human with visible radiation scarring and leathery, slightly decayed skin. "
        "Their facial features are worn and aged, but they still retain human expressions and emotions. "
        "Their eyes may appear sunken, and their skin tone varies from pale to ashen, "
        "but they remain distinctly humanoid."
    ),
    RaceOption.SUPER_MUTANT: (
        "A Super Mutant is a large, muscular humanoid with green or dark green skin. "
        "Their body appears strengthened by mutation, giving them a powerful and bulky frame. "
        "They have rough skin and battle scars but still maintain an expressive, intelligent face."
    ),
    RaceOption.SYNTH: (
        "A Synth is a humanoid with artificial skin, appearing almost indistinguishable from a human. "
        "Some areas may have subtle seams or metallic plating, but their expressions and body "
        "language are fully natural, resembling a person with advanced cybernetic enhancements."
    ),
}
