import random

from faker import Faker

from app.schemas.common import JunkType, Rarity, WeaponType, WeaponSubtype

fake = Faker()


def create_fake_junk():
    return {
        "name": fake.word().capitalize(),
        "rarity": random.choice(list(Rarity)),  # noqa: S311
        "value": random.randint(1, 1000),  # noqa: S311
        "junk_type": random.choice(list(JunkType)),  # noqa: S311
        "description": fake.sentence(),
    }


def create_fake_outfit():
    return {
        "name": fake.word().capitalize(),
        "rarity": random.choice(list(Rarity)),  # noqa: S311
        "value": random.randint(1, 1000),  # noqa: S311
        # TODO: Add outfit type, stat, gender ...
    }


def create_fake_weapon():
    return {
        "name": fake.word().capitalize(),
        "rarity": random.choice(list(Rarity)),  # noqa: S311
        "value": random.randint(1, 1000),  # noqa: S311
        "weapon_type": random.choice(list(WeaponType)),  # noqa: S311
        "weapon_subtype": random.choice(list(WeaponSubtype)),  # noqa: S311
        "stat": random.choice(["strength", "agility", "intelligence"]),  # noqa: S311
        "damage_min": random.randint(1, 10),  # noqa: S311
        "damage_max": random.randint(11, 20),  # noqa: S311
    }
