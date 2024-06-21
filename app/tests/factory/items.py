import random

from faker import Faker

from app.schemas.common import GenderEnum, JunkTypeEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.tests.utils.utils import get_name_two_words

fake = Faker()


def create_fake_junk():
    return {
        "name": get_name_two_words(),
        "rarity": random.choice(list(RarityEnum)),
        "value": random.randint(1, 1_000),
        "junk_type": random.choice(list(JunkTypeEnum)),
        "description": fake.sentence(),
    }


def create_fake_outfit():
    return {
        "name": get_name_two_words(),
        "rarity": random.choice(list(RarityEnum)),
        "value": random.randint(1, 1_000),
        "outfit_type": random.choice(list(OutfitTypeEnum)),
        "gender": random.choice(list(GenderEnum)),
    }


def create_fake_weapon():
    return {
        "name": get_name_two_words(),
        "rarity": random.choice(list(RarityEnum)),
        "value": random.randint(1, 1_000),
        "weapon_type": random.choice(list(WeaponTypeEnum)),
        "weapon_subtype": random.choice(list(WeaponSubtypeEnum)),
        "stat": random.choice(["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]),
        "damage_min": random.randint(1, 10),
        "damage_max": random.randint(11, 20),
    }
