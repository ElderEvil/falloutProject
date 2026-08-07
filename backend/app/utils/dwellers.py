from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any

from faker import Faker

from app.schemas.common import AgeGroupEnum, GenderEnum
from app.schemas.dweller import LETTER_TO_STAT, STATS_RANGE_BY_RARITY, RarityEnum

fake: Faker = Faker()


def get_gender_based_name(gender: GenderEnum, faker: Faker | None = None) -> str:
    """Generate a gender-based first name for production use."""
    source = faker if faker is not None else fake
    return source.first_name_male() if gender == GenderEnum.MALE else source.first_name_female()


def get_stats_by_rarity(rarity: RarityEnum, rng: random.Random | None = None) -> dict[str, int]:
    """Generate stats based on rarity for production use."""
    source = rng if rng is not None else random
    stats_range: tuple[int, int] = STATS_RANGE_BY_RARITY[rarity]
    return {stat_name: source.randint(stats_range[0], stats_range[1]) for stat_name in LETTER_TO_STAT.values()}


def create_random_common_dweller(gender: GenderEnum | None = None, seed: int | None = None) -> dict[str, Any]:
    """Create a random common dweller for production use.

    When ``seed`` is provided the RNG and the Faker instance are seeded so the
    same call reproduces the same dweller (used by the pregen CLI ``--seed``).
    """
    rng: random.Random = random.Random(seed) if seed is not None else random
    faker: Faker = Faker() if seed is not None else fake
    if seed is not None:
        faker.seed_instance(seed)

    rarity = RarityEnum.COMMON
    gender = gender or rng.choice(list(GenderEnum))
    stats = get_stats_by_rarity(rarity, rng)
    age_group = rng.choice([AgeGroupEnum.ADULT, AgeGroupEnum.CHILD])
    is_adult = age_group == AgeGroupEnum.ADULT
    now = datetime.now(UTC).replace(tzinfo=None) if seed is None else datetime(2000, 1, 1)
    birth_date = now - timedelta(days=rng.randint(18 * 365, 80 * 365)) if is_adult else now
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
