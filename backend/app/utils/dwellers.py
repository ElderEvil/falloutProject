from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from faker import Faker

from app.core.enums import GenderEnum, RarityEnum, SynthTypeEnum
from app.core.game_config import game_config
from app.options.dweller_names import (
    SUPER_MUTANT_EPITHETS,
    SUPER_MUTANT_NAMES,
    SYNTH_DESIGNATION_PREFIXES,
)
from app.options.factions import FactionOption, faction_restrictions
from app.options.races import STATE_OF_BEING_OPTIONS, RaceOption, race_of
from app.schemas.dweller import LETTER_TO_STAT, STATS_RANGE_BY_RARITY
from app.utils.appearance_roll import inherit_appearance_for_child
from app.utils.leveling import calculate_xp_required

if TYPE_CHECKING:
    from types import ModuleType

fake: Faker = Faker()


def get_gender_based_name(gender: GenderEnum, faker: Faker | None = None) -> str:
    """Generate a gender-based first name for production use."""
    source = faker if faker is not None else fake
    return source.first_name_male() if gender == GenderEnum.MALE else source.first_name_female()


def get_super_mutant_name(state_of_being: str | None, rng: random.Random | ModuleType) -> str:
    """Pick a mutation-appropriate super mutant name, sometimes with an epithet."""
    state = state_of_being or "average"
    pool = SUPER_MUTANT_NAMES.get(state, SUPER_MUTANT_NAMES["average"])
    name = rng.choice(pool)
    if state == "mild":
        return name
    epithet_chance = 0.35 if state == "behemoth" else 0.25
    if rng.random() < epithet_chance:
        return f"{name} {rng.choice(SUPER_MUTANT_EPITHETS)}"
    return name


def get_synth_designation(rng: random.Random | ModuleType) -> str:
    """Return an Institute-style designation such as ``M7-62``."""
    return f"{rng.choice(SYNTH_DESIGNATION_PREFIXES)}{rng.randint(0, 9)}-{rng.randint(1, 99):02d}"


def get_race_based_name(
    race: RaceOption,
    state_of_being: str | None,
    gender: GenderEnum,
    faker: Faker,
    rng: random.Random | ModuleType,
) -> tuple[str, str | None]:
    """(first_name, last_name) from the race's canonical name source.

    Humans, ghouls and gen-3 synths keep Faker names; super mutants and visible synths use
    curated/procedural names so they don't read as modern real-world citizens.
    """
    if race == RaceOption.SUPER_MUTANT:
        return get_super_mutant_name(state_of_being, rng), None
    if race == RaceOption.SYNTH and state_of_being == SynthTypeEnum.GEN_1.value:
        return get_synth_designation(rng), None
    if race == RaceOption.SYNTH and state_of_being == SynthTypeEnum.GEN_2.value:
        if rng.random() < 0.25:
            return get_gender_based_name(gender, faker), faker.last_name()
        return get_synth_designation(rng), None
    return get_gender_based_name(gender, faker), faker.last_name()


def get_stats_by_rarity(rarity: RarityEnum, rng: random.Random | ModuleType | None = None) -> dict[str, int]:
    """Generate stats based on rarity for production use."""
    source = rng if rng is not None else random
    stats_range: tuple[int, int] = STATS_RANGE_BY_RARITY[rarity]
    return {stat_name: source.randint(stats_range[0], stats_range[1]) for stat_name in LETTER_TO_STAT.values()}


def _calendar_years_ago(value: datetime, years: int) -> datetime:
    """Return a calendar-year offset, handling leap-day birthdays."""
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, month=2, day=28)


def elder_birth_threshold(now: datetime) -> datetime:
    """Birth date at or before which a dweller counts as an elder."""
    return _calendar_years_ago(now, game_config.dweller.elder_age_years)


def roll_spawn_birth_date(now: datetime, rng: random.Random | ModuleType) -> datetime:
    """Birth date for a new arrival: most spawn under 30, a minority up to 80, so elders stay
    rare without disappearing.
    """
    years = rng.randint(18, 30) if rng.random() < 0.7 else rng.randint(31, 80)
    return _calendar_years_ago(now, years) + timedelta(days=rng.randint(0, 364))


def _identity_for_race(race: RaceOption, source: random.Random | ModuleType) -> dict[str, Any]:
    """Build a validator-passing race/faction/state_of_being identity for a chosen race."""
    if not game_config.features.faction_mechanics:
        faction = FactionOption.NONE
    elif race == RaceOption.HUMAN:
        faction_weights = game_config.dweller.human_faction_weights
        faction = source.choices(list(faction_weights), weights=list(faction_weights.values()))[0]
    else:
        faction = source.choice(faction_restrictions[race])
    identity: dict[str, Any] = {"race": race.value, "faction": FactionOption(faction).value}
    if states := STATE_OF_BEING_OPTIONS.get(race):
        state_values = [state.value for state in states]
        weights = game_config.dweller.get_state_weights(race.value)
        if weights:
            identity["state_of_being"] = source.choices(
                state_values, weights=[weights[value] for value in state_values]
            )[0]
        else:
            identity["state_of_being"] = source.choice(state_values)
    return identity


def _roll_identity(rng: random.Random | ModuleType) -> dict[str, Any]:
    """Roll race/faction/state_of_being from game_config weights using rng.

    Race follows DwellerConfig.race_weights (85/7/5/3 default). Humans draw from the
    vault_dweller-dominant human_faction_weights; non-humans uniformly from
    faction_restrictions[race] and carry a weighted state_of_being (STATE_OF_BEING_OPTIONS +
    state_weights). Every pair passes the DwellerVisualAttributes identity validator.
    """
    weights = game_config.dweller.get_race_weights()
    race = rng.choices(list(RaceOption), weights=[weights[r.value] for r in RaceOption])[0]
    return _identity_for_race(race, rng)


def roll_child_identity(mother: Any, father: Any, source: random.Random | ModuleType = random) -> dict[str, Any]:
    """Roll a newborn's identity: inherit one of the parents' races.

    Only humans are breeding-eligible, so the child's race is always a parent's; non-humans
    enter via recruitment, pregeneration and recycling, never births. Every pair passes the
    DwellerVisualAttributes identity validator.
    """
    parent_races = [race for race in (race_of(mother), race_of(father)) if race is not None] or [RaceOption.HUMAN]
    race = source.choice(parent_races)
    identity = _identity_for_race(race, source)
    identity.update(inherit_appearance_for_child(race, mother, father, source))
    return identity


def rarity_level_bounds(rarity: RarityEnum | str) -> tuple[int, int]:
    value = rarity.value if isinstance(rarity, RarityEnum) else str(rarity).lower()
    cfg = game_config.leveling
    bands = {
        RarityEnum.RARE.value: (cfg.rare_start_level_min, cfg.rare_start_level_max),
        RarityEnum.LEGENDARY.value: (cfg.legendary_start_level_min, cfg.legendary_start_level_max),
    }
    band = bands.get(value)
    if band is None:
        return 1, 1
    low, high = band
    high = min(high, cfg.max_level)
    low = min(low, high)
    return low, high


def clamp_level_for_rarity(rarity: RarityEnum | str, level: int) -> int:
    low, high = rarity_level_bounds(rarity)
    return max(low, min(int(level), high))


def level_progress(level: int) -> tuple[int, int]:
    return _max_health_for_level(level), calculate_xp_required(level)


def _max_health_for_level(level: int) -> int:
    """Health a dweller should hold at ``level`` under flat per-level gains."""
    return game_config.leveling.base_max_health + (level - 1) * game_config.leveling.hp_gain_per_level
