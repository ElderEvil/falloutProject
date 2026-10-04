import random

from faker import Faker

from app.core.enums import ADULT_AGE_GROUPS
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.tests.utils.utils import get_gender_based_name, get_stats_by_rarity

fake = Faker()


def create_fake_dweller():
    rarity = random.choice(list(RarityEnum))
    max_health = random.randint(50, 1_000)

    stats = get_stats_by_rarity(rarity)
    age_group = random.choice(list(AgeGroupEnum))

    return stats | {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "is_adult": age_group in ADULT_AGE_GROUPS,
        "age_group": age_group,
        "gender": random.choice(list(GenderEnum)),
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


def create_fake_adult_dweller():
    return create_fake_dweller() | {"is_adult": True, "age_group": AgeGroupEnum.ADULT}


def create_random_common_dweller(gender: GenderEnum | None = None):
    rarity = RarityEnum.COMMON
    gender = gender or random.choice(list(GenderEnum))
    stats = get_stats_by_rarity(rarity)
    return {
        "first_name": get_gender_based_name(gender),
        "last_name": fake.last_name(),
        "gender": gender,
        "rarity": rarity,
        "level": 1,
        "experience": 0,
        "max_health": 100,
        "health": 100,
        "happiness": 50,
        "is_adult": True,
        "age_group": AgeGroupEnum.ADULT,
        "visual_attributes": {"race": "human", "faction": "vault_dweller"},
    } | stats
