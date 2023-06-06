import random

import pytest
from faker import Faker

from app.schemas.common import Gender, JunkType, OutfitType, Rarity, RoomType, WeaponSubtype, WeaponType
from app.tests.utils.utils import get_gender_based_name, get_name_two_words, get_stats_by_rarity

fake = Faker()


def get_generic_items_data():
    return {
        "name": get_name_two_words(),
        "rarity": random.choice(list(Rarity)),
        "value": random.randint(1, 1000),
    }


@pytest.fixture(params=list(Rarity))
def rarity_fixture(request):  # noqa: ANN001
    return request.param


@pytest.fixture(params=list(Gender))
def gender_fixture(request):  # noqa: ANN001
    return request.param


@pytest.fixture(name="dweller_data")
def dweller_fixture(gender_fixture, rarity_fixture):  # noqa: ANN001
    gender = gender_fixture
    rarity = rarity_fixture
    stats = get_stats_by_rarity(rarity)

    max_health = random.randint(50, 1000)
    health = random.randint(0, max_health)

    return stats | {
        "first_name": get_gender_based_name(gender),
        "last_name": fake.last_name(),
        "gender": gender.value,
        "rarity": rarity.value,
        "level": random.randint(1, 50),
        "experience": random.randint(0, 1000),
        "max_health": max_health,
        "health": health,
        "happiness": random.randint(10, 100),
        "is_adult": random.choice([True, False]),
    }


@pytest.fixture(name="room_data", params=list(RoomType))
def room_fixture(request):  # noqa: ANN001
    room_type = request.param
    return {
        "name": get_name_two_words(),
        "category": room_type,
        "ability": random.choice(["S", "P", "E", "C", "I", "A", "L"]),
        "population_required": random.randint(12, 100),
        "base_cost": random.randint(100, 10_000),
        "incremental_cost": random.randint(25, 5_000),
        "tier": 1,
        "max_tier": random.randint(1, 3),
        "t2_upgrade_cost": random.randint(500, 50_000),
        "t3_upgrade_cost": random.randint(1500, 150_000),
        "output": random.randint(1, 100),
        "size": random.randint(3, 9),
    }


@pytest.fixture(name="junk_data")
def junk_fixture():
    junk_type = random.choice(list(JunkType))
    item_data = get_generic_items_data()
    return item_data | {
        "junk_type": junk_type,
        "description": fake.sentence(),
    }


@pytest.fixture(name="outfit_data")
def outfit_fixture():
    outfit_type = random.choice(list(OutfitType))
    item_data = get_generic_items_data()
    return item_data | {"description": fake.sentence(), "outfit_type": outfit_type}


@pytest.fixture(name="weapon_data")
def weapon_fixture():
    weapon_type = random.choice(list(WeaponType))
    weapon_subtype = random.choice(list(WeaponSubtype))
    item_data = get_generic_items_data()
    return item_data | {
        "description": fake.sentence(),
        "weapon_type": weapon_type,
        "weapon_subtype": weapon_subtype,
        "stat": random.choice(["S", "P", "E", "C", "I", "A", "L"]),
        "damage_min": random.randint(1, 10),
        "damage_max": random.randint(11, 20),
    }
