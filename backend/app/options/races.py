"""Race and state-of-being enums with lore descriptions."""

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
    PARTIALLY_FERAL = "partially_feral"
    FULLY_FERAL = "fully_feral"


class SuperMutantMutation(StrEnum):
    """State of being for Super Mutant characters."""

    MILD = "mild_mutation"
    SEVERE = "severe_mutation"
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
