import random

from faker import Faker

from app.schemas.common import JunkType, Rarity, WeaponType, WeaponSubtype

fake = Faker()


def create_fake_junk():
    return {
        "name": fake.word().capitalize(),
        "rarity": random.choice(list(Rarity)),
        "value": random.randint(1, 1000),
        "junk_type": random.choice(list(JunkType)),
        "description": fake.sentence(),
    }


def create_fake_outfit():
    return {
        "name": fake.word().capitalize(),
        "rarity": random.choice(list(Rarity)),
        "value": random.randint(1, 1000),
        # TODO: Add outfit type, stat, gender ...
    }


def create_fake_weapon():
    return {
        "name": fake.word().capitalize(),
        "rarity": random.choice(list(Rarity)),
        "value": random.randint(1, 1000),
        "weapon_type": random.choice(list(WeaponType)),
        "weapon_subtype": random.choice(list(WeaponSubtype)),
        "stat": random.choice(["strength", "agility", "intelligence"]),
        "damage_min": random.randint(1, 10),
        "damage_max": random.randint(11, 20),
    }
