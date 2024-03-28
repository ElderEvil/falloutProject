import random

from faker import Faker

from app.schemas.common import Gender, Rarity
from app.tests.utils.utils import get_stats_by_rarity, get_gender_based_name

fake = Faker()


def create_fake_dweller():
    rarity = random.choice(list(Rarity))
    max_health = random.randint(50, 1_000)

    stats = get_stats_by_rarity(rarity)

    return stats | {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "is_adult": random.choice([True, False]),
        "gender": random.choice(list(Gender)),
        "rarity": rarity,
        "level": random.randint(1, 50),
        "experience": random.randint(0, 1_000),
        "max_health": random.randint(50, 1_000),
        "health": random.randint(50, max_health),
        "radiation": random.randint(0, 1_000),
        "happiness": random.randint(10, 100),
        "stimpack": random.randint(0, 15),
        "radaway": random.randint(0, 15),
    }


def create_random_common_dweller(gender: Gender | None = None):
    rarity = Rarity.common
    gender = gender or random.choice(list(Gender))
    stats = get_stats_by_rarity(rarity)
    return {
        "first_name": get_gender_based_name(gender),
        "last_name": fake.last_name,
        "gender": gender,
        "rarity": rarity,
        "level": 1,
        "experience": 0,
        "max_health": 100,
        "health": 100,
        "happiness": 50,
        "is_adult": True,
    } | stats
