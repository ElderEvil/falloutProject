from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any

from faker import Faker

from app.core.game_config import game_config
from app.schemas.common import AgeGroupEnum, GenderEnum
from app.schemas.dweller import LETTER_TO_STAT, STATS_RANGE_BY_RARITY, RarityEnum

fake: Faker = Faker()

#: Deterministic pool of wasteland place names used in procedural bios. Kept out
#: of ``GENERIC_ORIGIN_SKIP`` (no "", "wasteland", "unknown") so every picked
#: origin/visited name is registrable on the world map.
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


def _procedural_bio_places(rng: random.Random, rarity: RarityEnum) -> tuple[str, list[str]]:
    """Pick a deterministic origin + rarity-scaled visited places for a bio.

    The visited count follows ``game_config.bio.max_visited`` so common dwellers
    mention fewer places than legendaries; the same ``rng`` stream makes the
    result reproducible for a given seed.
    """
    origin = rng.choice(_PLACE_POOL)
    visited_count = game_config.bio.max_visited(rarity.value)
    remaining = [place for place in _PLACE_POOL if place != origin]
    visited = rng.sample(remaining, min(visited_count, len(remaining)))
    return origin, visited


def _render_template_bio(origin: str, visited: list[str]) -> str:
    if not visited:
        return f"Born in {origin}. Before the vault, I wandered the wastes alone."
    if len(visited) == 1:
        return f"Born in {origin}. Before the vault, I wandered through {visited[0]}."
    return f"Born in {origin}. Before the vault, I wandered through {', '.join(visited[:-1])}, and {visited[-1]}."


def get_gender_based_name(gender: GenderEnum, faker: Faker | None = None) -> str:
    """Generate a gender-based first name for production use."""
    source = faker if faker is not None else fake
    return source.first_name_male() if gender == GenderEnum.MALE else source.first_name_female()


def get_stats_by_rarity(rarity: RarityEnum, rng: random.Random | None = None) -> dict[str, int]:
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


def create_random_common_dweller(
    gender: GenderEnum | None = None, seed: int | None = None, rarity: RarityEnum = RarityEnum.COMMON
) -> dict[str, Any]:
    """Create a random common dweller for production use.

    When ``seed`` is provided the RNG and the Faker instance are seeded so the
    same call reproduces the same dweller (used by the pregen CLI ``--seed``).
    """
    rng: random.Random = random.Random(seed) if seed is not None else random
    faker: Faker = Faker() if seed is not None else fake
    if seed is not None:
        faker.seed_instance(seed)

    gender = gender or rng.choice(list(GenderEnum))
    stats = get_stats_by_rarity(rarity, rng)
    # Procedurally generated dwellers represent wasteland recruits. Children
    # enter the vault only through the breeding lifecycle.
    age_group = AgeGroupEnum.ADULT
    is_adult = True
    now = datetime.now(UTC).replace(tzinfo=None) if seed is None else datetime(2000, 1, 1)
    oldest_birth_date = _calendar_years_ago(now, 80)
    youngest_birth_date = _calendar_years_ago(now, 18)
    birth_date = oldest_birth_date + timedelta(days=rng.randint(0, (youngest_birth_date - oldest_birth_date).days))
    origin, visited = _procedural_bio_places(rng, rarity)
    return {
        "first_name": get_gender_based_name(gender, faker),
        "last_name": faker.last_name(),
        "is_adult": is_adult,
        "age_group": age_group,
        "birth_date": birth_date,
        "gender": gender,
        "rarity": rarity,
        "level": 1,
        "experience": 0,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 50,
        "stimpack": 0,
        "radaway": 0,
        "visual_attributes": {"race": "human", "faction": "vault_dweller"},
        "bio": _render_template_bio(origin, visited),
        # Reserved for the caller (crud.create_random) to register map places;
        # never a Dweller column, so it must be popped before model construction.
        "_bio_places": (origin, visited),
        **stats,
    }


def group_dwellers_by_room(dwellers: list[Any]) -> dict[str, list[Any]]:
    """Group dwellers by their room_id."""
    room_dwellers: dict[str, list[Any]] = {}
    for dweller in dwellers:
        if dweller.room_id not in room_dwellers:
            room_dwellers[dweller.room_id] = []
        room_dwellers[dweller.room_id].append(dweller)
    return room_dwellers
