import random

from faker import Faker

from app.schemas.common import Gender, JunkType, OutfitType, Rarity, WeaponSubtype, WeaponType
from app.tests.utils.utils import get_name_two_words

fake = Faker()


def create_fake_junk():
    return {
        "name": get_name_two_words(),
        "rarity": random.choice(list(Rarity)),
        "value": random.randint(1, 1000),
        "junk_type": random.choice(list(JunkType)),
        "description": fake.sentence(),
    }


def create_fake_outfit():
    return {
        "name": get_name_two_words(),
        "rarity": random.choice(list(Rarity)),
        "value": random.randint(1, 1000),
        "outfit_type": random.choice(list(OutfitType)),
        "gender": random.choice(list(Gender)),
    }


def create_fake_weapon():
    return {
        "name": get_name_two_words(),
        "rarity": random.choice(list(Rarity)),
        "value": random.randint(1, 1000),
        "weapon_type": random.choice(list(WeaponType)),
        "weapon_subtype": random.choice(list(WeaponSubtype)),
        "stat": random.choice(["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]),
        "damage_min": random.randint(1, 10),
        "damage_max": random.randint(11, 20),
    }
