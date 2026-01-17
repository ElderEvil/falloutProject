import random
from typing import Any

from faker import Faker

from app.schemas.common import GenderEnum
from app.schemas.dweller import LETTER_TO_STAT, STATS_RANGE_BY_RARITY, RarityEnum

fake = Faker()


def get_gender_based_name(gender: GenderEnum):
    """Generate a gender-based first name for production use."""
    return fake.first_name_male() if gender == GenderEnum.MALE else fake.first_name_female()


def get_stats_by_rarity(rarity: RarityEnum) -> dict:
    """Generate stats based on rarity for production use."""
    stats_range = STATS_RANGE_BY_RARITY[rarity]
    return {stat_name: random.randint(stats_range[0], stats_range[1]) for stat_name in LETTER_TO_STAT.values()}


def create_random_common_dweller(gender: GenderEnum | None = None) -> dict[str, Any]:
    """Create a random common dweller for production use."""

    rarity = RarityEnum.COMMON
    gender = gender or random.choice(list(GenderEnum))
    stats = get_stats_by_rarity(rarity)
    max_health = random.randint(50, 1_000)
    health = random.randint(50, max_health)
    return {
        "first_name": get_gender_based_name(gender),
        "last_name": fake.last_name(),
        "is_adult": random.choice([True, False]),
        "gender": gender,
        "rarity": rarity,
        "level": random.randint(1, 50),
        "experience": random.randint(0, 1_000),
        "max_health": max_health,
        "health": health,
        "radiation": random.randint(0, 1_000),
        "happiness": random.randint(10, 100),
        "stimpack": random.randint(0, 15),
        "radaway": random.randint(0, 15),
        **stats,
    }
