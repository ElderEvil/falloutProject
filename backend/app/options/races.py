"""Race and state-of-being options with lore descriptions.

The enums are defined once in ``app/core/enums.py``; this module re-exports the
race option under its domain name and owns the race-specific data (descriptions,
modifiers, breeding eligibility).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.core.enums import (
    GhoulFeralnessEnum,
    RaceEnum,
    SuperMutantMutationEnum,
    SynthTypeEnum,
)

RaceOption = RaceEnum

# Union type for state_of_being field
STATE_OF_BEING_OPTIONS: dict[RaceOption, list[StrEnum]] = {
    RaceOption.GHOUL: list(GhoulFeralnessEnum),
    RaceOption.SUPER_MUTANT: list(SuperMutantMutationEnum),
    RaceOption.SYNTH: list(SynthTypeEnum),
}

STATE_OF_BEING_VALUES: dict[RaceOption, list[str]] = {
    race: [s.value for s in states] for race, states in STATE_OF_BEING_OPTIONS.items()
}

#: Whether a race can conceive. Non-humans do not give birth; they enter the
#: population through recruitment, pregeneration, and recycling.
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
    RaceOption.SUPER_MUTANT: RaceModifiers(strength=3, endurance=2, perception=-2, radiation_immune=True),
    RaceOption.SYNTH: RaceModifiers(perception=1, intelligence=1, radiation_immune=True),
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


def state_of_being_of(entity: object) -> str | None:
    """Read an entity's state-of-being string from ``visual_attributes``, if present."""
    attrs = getattr(entity, "visual_attributes", None)
    raw = attrs.get("state_of_being") if isinstance(attrs, dict) else None
    return raw if isinstance(raw, str) and raw else None


#: Fallout-universe senescence rule: only humans grow old. Ghouls are
#: radiation-scarred ageless (they wear and may go feral, but never become
#: elders), super mutants are FEV-sterile ageless (they mutate toward behemoth
#: instead), synths are machines. Youth maturation still runs for every race so
#: a mutated newborn can reach adulthood; only the ADULT -> ELDER step is gated.
AGELESS_RACES: frozenset[RaceOption] = frozenset({RaceOption.GHOUL, RaceOption.SUPER_MUTANT, RaceOption.SYNTH})


def is_ageless(race: RaceOption | str | None) -> bool:
    """Whether a race never senesces into the elder age group (calculation-only, no columns)."""
    try:
        return RaceOption(race) in AGELESS_RACES if race is not None else False
    except ValueError:
        return False


def can_use_radaway(entity: object) -> bool:
    """Only races that can accumulate radiation can use RadAway."""
    return not modifiers_for_race(entity).radiation_immune


def can_take_purposeful_action(entity: object) -> bool:
    """Feral ghouls and behemoths cannot initiate intentional chat actions."""
    race = race_of(entity)
    return (race, state_of_being_of(entity)) not in {
        (RaceOption.GHOUL, GhoulFeralnessEnum.FERAL.value),
        (RaceOption.SUPER_MUTANT, SuperMutantMutationEnum.BEHEMOTH.value),
    }


def chronological_years(birth_date: datetime | None, now: datetime | None = None) -> float | None:
    """Real age in years from ``birth_date``; None when unknown.

    This is the *real* age. ``age_group`` is the *visual* age the UI shows.
    For ghouls the two diverge on purpose: a ghoul can look worn at a visual
    adult/elder while the real span covers centuries, and feral risk must read
    the real span, never the visual group. No persistence — derive on read.
    """
    if birth_date is None:
        return None
    ref = now if now is not None else datetime.now(UTC)
    # Persisted dates are naive UTC; explicit aware dates are normalized to the same convention.
    birth_utc = birth_date.astimezone(UTC).replace(tzinfo=None) if birth_date.tzinfo else birth_date
    ref_utc = ref.astimezone(UTC).replace(tzinfo=None) if ref.tzinfo else ref
    return max(0.0, (ref_utc - birth_utc).total_seconds() / 31_556_952.0)


def visual_vs_real_age(entity: object, now: datetime | None = None) -> dict[str, Any]:
    """Visual (``age_group``) vs real (``birth_date``) age for one entity.

    Documented seam for the future radiation -> feral-pressure calculation:
    when that lands it must take ``real_years`` plus cumulative exposure into
    account, because ghoul ``radiation`` stays 0 (immunity) and cannot drive it
    from the stored value. Currently pure description, no behavior change.
    """
    return {
        "visual": getattr(entity, "age_group", None),
        "real_years": chronological_years(getattr(entity, "birth_date", None), now),
        "ageless": is_ageless(race_of(entity)),
    }


#: State-of-being SPECIAL deltas applied on read beside the racial baseline.
#: Small by design; a balance pass follows play-testing. Keys are
#: (race value, state value); absent pairs mean no extra delta.
STATE_STAT_DELTAS: dict[tuple[str, str], dict[str, int]] = {
    ("ghoul", "wild"): {"charisma": -2, "intelligence": -2, "perception": 1, "agility": 1},
    ("ghoul", "feral"): {
        "strength": 1,
        "perception": 2,
        "endurance": 1,
        "agility": 1,
        "charisma": -4,
        "intelligence": -4,
    },
    ("super_mutant", "average"): {"strength": 1},
    ("super_mutant", "behemoth"): {"strength": 2, "endurance": 1, "intelligence": -2, "charisma": -2},
    ("synth", "gen_1"): {"strength": 1, "charisma": -2, "intelligence": -1},
    ("synth", "gen_2"): {"strength": 1, "charisma": -1},
}


def state_stat_deltas_for(entity: object) -> dict[str, int]:
    """Extra SPECIAL deltas for an entity's state-of-being; empty when none apply."""
    race = race_of(entity)
    state = state_of_being_of(entity)
    if race is None or state is None:
        return {}
    return dict(STATE_STAT_DELTAS.get((race.value, state), {}))


#: Synth models whose artificial nature is visible; the rest pass as human.
VISIBLE_SYNTH_STATES: frozenset[str] = frozenset({SynthTypeEnum.GEN_1.value, SynthTypeEnum.GEN_2.value})


def passes_as_human(race: RaceOption | str | None, state_of_being: str | None) -> bool:
    """Whether a race must present as human (Gen 3 synths; an unknown model fails the same way)."""
    return race == RaceOption.SYNTH and state_of_being not in VISIBLE_SYNTH_STATES


def can_breed(entity: object) -> bool:
    """Whether an entity's race may conceive; entities without a race default to human."""
    return BREEDING_ELIGIBLE.get(race_of(entity) or RaceOption.HUMAN, False)


class SocialPresence(StrEnum):
    """How a dweller's race and state read to coworkers."""

    NORMAL = "normal"
    GHOUL = "ghoul"
    FERAL = "feral"
    MUTANT = "mutant"
    BEHEMOTH = "behemoth"
    SYNTH_GEN_1 = "synth_gen_1"
    SYNTH_GEN_2 = "synth_gen_2"


class DiscomfortSeverity(StrEnum):
    """Severity of a coworker's unease around a feral ghoul or super mutant."""

    MILD = "mild"
    MODERATE = "moderate"
    STRONG = "strong"

    @property
    def rank(self) -> int:
        """Ordering for taking the worst discomfort in a room."""
        return list(type(self)).index(self)


@dataclass(frozen=True)
class Discomfort:
    """One pair's unease: how strong it is and which presence causes it."""

    severity: DiscomfortSeverity
    source: SocialPresence


def social_presence(entity: object) -> SocialPresence:
    """Classify a dweller for social-friction rules."""
    race = race_of(entity) or RaceOption.HUMAN
    state = state_of_being_of(entity)
    if race == RaceOption.GHOUL:
        return SocialPresence.FERAL if state == GhoulFeralnessEnum.FERAL.value else SocialPresence.GHOUL
    if race == RaceOption.SUPER_MUTANT:
        return SocialPresence.BEHEMOTH if state == SuperMutantMutationEnum.BEHEMOTH.value else SocialPresence.MUTANT
    if race == RaceOption.SYNTH:
        if state == SynthTypeEnum.GEN_1.value:
            return SocialPresence.SYNTH_GEN_1
        if state == SynthTypeEnum.GEN_2.value:
            return SocialPresence.SYNTH_GEN_2
    return SocialPresence.NORMAL


def _same_monster_kind(left: SocialPresence, right: SocialPresence) -> bool:
    if left == right:
        return True
    super_mutants = {SocialPresence.MUTANT, SocialPresence.BEHEMOTH}
    return left in super_mutants and right in super_mutants


def discomfort_between(entity_a: object, entity_b: object) -> Discomfort | None:
    """Pair unease from feral ghouls and super mutants; None when they are at ease."""
    left = social_presence(entity_a)
    right = social_presence(entity_b)
    if _same_monster_kind(left, right):
        return None
    presences = {left, right}
    if SocialPresence.FERAL in presences:
        severity = (
            DiscomfortSeverity.MILD
            if presences == {SocialPresence.FERAL, SocialPresence.GHOUL}
            else DiscomfortSeverity.STRONG
        )
        return Discomfort(severity=severity, source=SocialPresence.FERAL)
    if SocialPresence.BEHEMOTH in presences:
        return Discomfort(severity=DiscomfortSeverity.STRONG, source=SocialPresence.BEHEMOTH)
    if SocialPresence.MUTANT in presences:
        return Discomfort(severity=DiscomfortSeverity.MODERATE, source=SocialPresence.MUTANT)
    if SocialPresence.SYNTH_GEN_1 in presences:
        return Discomfort(severity=DiscomfortSeverity.MODERATE, source=SocialPresence.SYNTH_GEN_1)
    if SocialPresence.SYNTH_GEN_2 in presences:
        return Discomfort(severity=DiscomfortSeverity.MILD, source=SocialPresence.SYNTH_GEN_2)
    return None


@dataclass(frozen=True)
class DiscomfortEffect:
    """Mechanical unease for one severity, declared beside the race data."""

    chemistry_penalty: float
    happiness_penalty: float
    production_multiplier: float


#: Severity-keyed effects; a balance pass follows play-testing, like RACE_MODIFIERS.
DISCOMFORT_EFFECTS: dict[DiscomfortSeverity, DiscomfortEffect] = {
    DiscomfortSeverity.MILD: DiscomfortEffect(
        chemistry_penalty=0.10, happiness_penalty=0.5, production_multiplier=0.97
    ),
    DiscomfortSeverity.MODERATE: DiscomfortEffect(
        chemistry_penalty=0.15, happiness_penalty=1.0, production_multiplier=0.90
    ),
    DiscomfortSeverity.STRONG: DiscomfortEffect(
        chemistry_penalty=0.25, happiness_penalty=1.5, production_multiplier=0.85
    ),
}

#: Lowest combined discomfort/rival production multiplier for one room.
DISCOMFORT_PRODUCTION_FLOOR = 0.75


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
