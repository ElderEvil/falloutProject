import random

from faker import Faker

from app.schemas.common import Gender, Rarity
from app.schemas.dweller import LETTER_TO_STAT, STATS_RANGE_BY_RARITY

fake = Faker()


def get_stats_by_rarity(rarity: Rarity):
    min_value, max_value = STATS_RANGE_BY_RARITY[rarity]
    return {stat: random.randint(min_value, max_value) for stat in LETTER_TO_STAT.values()}


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
