import random

from faker import Faker

from app.schemas.common import Gender, Rarity
from app.tests.utils.utils import get_stats_by_rarity, get_gender_based_name

fake = Faker()


def create_fake_dweller():
    first_name = fake.first_name()
    last_name = fake.last_name()
    gender = random.choice(list(Gender))
    rarity = random.choice(list(Rarity))
    level = random.randint(1, 50)
    experience = random.randint(0, 1000)
    max_health = random.randint(50, 1000)
    health = random.randint(0, max_health)
    happiness = random.randint(10, 100)
    is_adult = random.choice([True, False])

    stats = get_stats_by_rarity(rarity)

    return stats | {
        "first_name": first_name,
        "last_name": last_name,
        "gender": gender,
        "rarity": rarity,
        "level": level,
        "experience": experience,
        "max_health": max_health,
        "health": health,
        "happiness": happiness,
        "is_adult": is_adult,
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
