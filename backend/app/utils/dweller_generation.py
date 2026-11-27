"""Build dweller payloads for random arrivals and curated templates."""

from __future__ import annotations

import random
from datetime import datetime
from typing import TYPE_CHECKING, Any

from faker import Faker

from app.core.enums import AgeGroupEnum, ContentProvenanceEnum, GenderEnum, RarityEnum
from app.core.game_config import game_config
from app.options.presets import archetypes
from app.options.races import RaceOption, is_ageless
from app.utils.appearance_roll import complete_appearance, describe_appearance, roll_appearance
from app.utils.bios import maybe_zone_rumor, render_bio
from app.utils.dwellers import (
    _max_health_for_level,
    _roll_identity,
    elder_birth_threshold,
    fake,
    get_race_based_name,
    get_stats_by_rarity,
    rarity_level_bounds,
    roll_spawn_birth_date,
)
from app.utils.leveling import calculate_xp_required
from app.utils.time import utcnow

if TYPE_CHECKING:
    from types import ModuleType

    from app.schemas.dweller_catalog import DwellerArchetype

# : Deterministic pool of wasteland place names used in procedural bios. Kept out
# : of ``GENERIC_ORIGIN_SKIP`` (no "", "wasteland", "unknown") so every picked
# : origin/visited name is registrable on the world map.
_PLACE_POOL: tuple[str, ...] = (
    "Megaton",
    "Rivet City",
    "Tenpenny Tower",
    "Paradise Falls",
    "Canterbury Commons",
    "Big Town",
    "Little Lamplight",
    "Goodneighbor",
    "Diamond City",
    "The Slog",
    "Bunker Hill",
    "Republic of Dave",
    "Arefu",
    "Nuka-Cola Plant",
)


def _procedural_bio_places(rng: random.Random | ModuleType, rarity: RarityEnum) -> tuple[str, list[str]]:
    """Deterministic origin + rarity-scaled visited places for a bio.

    Visited count follows game_config.bio.max_visited (commons mention fewer places than
    legendaries); the same rng stream reproduces results for a given seed.
    """
    origin = rng.choice(_PLACE_POOL)
    visited_count = game_config.bio.max_visited(rarity.value)
    remaining = [place for place in _PLACE_POOL if place != origin]
    visited = rng.sample(remaining, min(visited_count, len(remaining)))
    return origin, visited


def _race_from_attributes(attrs: dict[str, Any] | None) -> RaceOption | None:
    """Read a race from stored visual attributes; None when absent or invalid."""
    raw = (attrs or {}).get("race")
    try:
        return RaceOption(raw) if raw is not None else None
    except ValueError:
        return None


def _rarity_start_level(rarity: RarityEnum | str, rng: random.Random | ModuleType) -> int:
    """Starting level for a dweller of the given rarity (commons start at 1)."""
    low, high = rarity_level_bounds(rarity)
    return rng.randint(low, high)


def _pick_archetype_for_race(race: RaceOption, rng: random.Random | ModuleType) -> DwellerArchetype | None:
    """Weighted random archetype for the race, or None; skips empty appearance pools.

    The record supplies appearance and personality only — identity faction stays from
    _roll_identity.
    """
    candidates = [entry for entry in archetypes.values() if entry["race"] == race and entry["appearance_pools"]]
    if not candidates:
        return None
    return rng.choices(candidates, weights=[entry["weight"] for entry in candidates], k=1)[0]


def create_random_common_dweller(
    gender: GenderEnum | None = None, seed: int | None = None, rarity: RarityEnum = RarityEnum.COMMON
) -> dict[str, Any]:
    """Create a random common dweller for production use.

    With seed, the RNG and Faker instance are seeded so the same call reproduces the same
    dweller (pregen CLI --seed).
    """
    rng: random.Random | ModuleType = random.Random(seed) if seed is not None else random
    faker: Faker = Faker() if seed is not None else fake
    if seed is not None:
        faker.seed_instance(seed)

    gender = gender or rng.choice(list(GenderEnum))
    stats = get_stats_by_rarity(rarity, rng)
    now = utcnow() if seed is None else datetime(2000, 1, 1)
    birth_date = roll_spawn_birth_date(now, rng)
    identity = _roll_identity(rng)
    # Non-humans never senesce: visual freezes at adult while birth_date keeps the real span for future feral-pressure
    # math.
    if is_ageless(_race_from_attributes(identity)):
        age_group = AgeGroupEnum.ADULT
    else:
        age_group = AgeGroupEnum.ELDER if birth_date <= elder_birth_threshold(now) else AgeGroupEnum.ADULT

    race = _race_from_attributes(identity) or RaceOption.HUMAN
    # Pick archetype after race is known.
    archetype = _pick_archetype_for_race(race, rng)
    appearance_pools = archetype["appearance_pools"] if archetype else None

    identity.update(roll_appearance(race, gender, rng, age_group, appearance_pools=appearance_pools))

    origin, visited = _procedural_bio_places(rng, rarity)
    bio = render_bio(origin, visited, race=race, rng=rng)

    if archetype and archetype["personality_lines"]:
        appearance_desc = describe_appearance(identity, gender, race)
        personality = rng.choice(archetype["personality_lines"])
        bio = f"{bio} {appearance_desc} {personality}"

    if rumor := maybe_zone_rumor(rng, game_config.bio.zone_rumor_chance):
        bio = f"{bio} {rumor}"

    level = _rarity_start_level(rarity, rng)
    starting_health = _max_health_for_level(level)
    starting_xp = calculate_xp_required(level)
    first_name, last_name = get_race_based_name(race, identity.get("state_of_being"), gender, faker, rng)
    return {
        "first_name": first_name,
        "last_name": last_name,
        "age_group": age_group,
        "birth_date": birth_date,
        "gender": gender,
        "rarity": rarity,
        "level": level,
        "experience": starting_xp,
        "max_health": starting_health,
        "health": starting_health,
        "radiation": 0,
        "happiness": 50,
        "stimpack": 0,
        "radaway": 0,
        "visual_attributes": identity,
        "bio": bio,
        "_bio_places": (origin, visited),
        "content_provenance": ContentProvenanceEnum.GENERATED,
        **stats,
    }


def create_dweller_from_template(
    template: Any,
    seed: int | None = None,
) -> dict[str, Any]:
    """Build a persistable dweller dict from a curated DwellerTemplate.

    Template SPECIAL, bio, visuals and map metadata are authoritative; birth date and health
    are synthesized so the row is immediately playable.
    """
    from app.schemas.dweller import DwellerTemplate

    if not isinstance(template, DwellerTemplate):
        raise TypeError("template must be a DwellerTemplate")
    payload, origin, visited = template.to_create_payload()
    data: dict[str, Any] = payload.model_dump(exclude_none=False)
    # Weapon/outfit are template metadata for item creation, not Dweller columns.
    data.pop("weapon", None)
    data.pop("outfit", None)
    # Visual attributes from DwellerTemplate may be a validated model; store as plain dict for JSONB.
    va = data.get("visual_attributes")
    if isinstance(va, dict):
        data["visual_attributes"] = va
    elif va is not None and hasattr(va, "model_dump"):
        data["visual_attributes"] = va.model_dump(exclude_none=False)  # type: ignore[union-attr]
    rng = random.Random(seed) if seed is not None else random
    now = utcnow() if seed is None else datetime(2000, 1, 1)
    if data.get("birth_date") is None:
        data["birth_date"] = roll_spawn_birth_date(now, rng)
    data.setdefault("age_group", AgeGroupEnum.ADULT)
    data.setdefault("level", 1)
    data.setdefault("experience", 0)
    data.setdefault("max_health", 100)
    data.setdefault("health", 100)
    data.setdefault("radiation", 0)
    data.setdefault("happiness", 50)
    # Rare/legendary templates arrive experienced, with health matching the levels they already carry (flat per-level
    # gains).
    start_level = _rarity_start_level(template.rarity, rng)
    if start_level > 1:
        data["level"] = start_level
        data["max_health"] = _max_health_for_level(start_level)
        data["health"] = data["max_health"]
        data["experience"] = calculate_xp_required(start_level)
    data["visual_attributes"] = complete_appearance(data, rng)
    data["content_provenance"] = ContentProvenanceEnum.CURATED
    data["_bio_places"] = (origin, visited) if origin or visited else None
    if not data.get("bio"):
        origin_fallback, visited_fallback = origin or "Vault 111", visited or []
        attrs = data.get("visual_attributes")
        data["bio"] = render_bio(
            origin_fallback,
            visited_fallback,
            race=_race_from_attributes(attrs if isinstance(attrs, dict) else None),
            rng=rng,
        )
        if data["_bio_places"] is None:
            data["_bio_places"] = (origin_fallback, visited_fallback)
    return data
