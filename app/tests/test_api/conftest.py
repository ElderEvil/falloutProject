import random

import pytest
import pytest_asyncio
from faker import Faker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.user import User
from app.models.vault import Vault
from app.schemas.common import Gender, JunkType, OutfitType, Rarity, RoomType, WeaponSubtype, WeaponType, SPECIAL
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreate
from app.tests.utils.utils import get_gender_based_name, get_name_two_words, get_stats_by_rarity

fake = Faker()


def get_generic_items_data():
    return {
        "name": get_name_two_words(),
        "rarity": random.choice(list(Rarity)),
        "value": random.randint(1, 1000),
    }


@pytest.fixture(name="vault_data")
def vault_data_fixture(user: User):
    return {
        "name": random.randint(1, 1000),
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
        "power": random.randint(0, 100),
        "food": random.randint(0, 100),
        "water": random.randint(0, 100),
    }


@pytest.fixture(name="room_data")
def room_data_fixture():
    return {
        "name": get_name_two_words(),
        "category": random.choice(list(RoomType)),
        "ability": random.choice([*list(SPECIAL), None]),
        "population_required": random.randint(12, 100),
        "base_cost": random.randint(100, 10_000),
        "incremental_cost": random.randint(25, 5_000),
        "t2_upgrade_cost": random.randint(500, 50_000),
        "t3_upgrade_cost": random.randint(1500, 150_000),
        "output": str(random.randint(1, 100)),
        "size": random.randint(3, 9),
        "tier": 1,
        "max_tier": random.randint(1, 3),
    }


@pytest.fixture(name="dweller_data")
def dweller_data_fixture():
    gender = random.choice(list(Gender))
    rarity = random.choice(list(Rarity))
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


@pytest.fixture(name="junk_data")
def junk_fixture():
    item_data = get_generic_items_data()
    return item_data | {
        "junk_type": random.choice(list(JunkType)),
        "description": fake.sentence(),
    }


@pytest.fixture(name="outfit_data")
def outfit_fixture():
    item_data = get_generic_items_data()
    return item_data | {"description": fake.sentence(), "outfit_type": random.choice(list(OutfitType))}


@pytest.fixture(name="weapon_data")
def weapon_fixture():
    item_data = get_generic_items_data()
    return item_data | {
        "description": fake.sentence(),
        "weapon_type": random.choice(list(WeaponType)),
        "weapon_subtype": random.choice(list(WeaponSubtype)),
        "stat": random.choice(["S", "P", "E", "C", "I", "A", "L"]),
        "damage_min": random.randint(1, 10),
        "damage_max": random.randint(11, 20),
    }


@pytest_asyncio.fixture(name="user")
async def user_fixture(async_session: AsyncSession) -> User:
    user_obj = UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password())
    return await crud.user.create(db_session=async_session, obj_in=user_obj)


@pytest_asyncio.fixture(name="vault")
async def vault_fixture(async_session: AsyncSession, user: User, vault_data: dict) -> Vault:
    vault_obj = VaultCreate(**vault_data | {"user_id": user.id})
    return await crud.vault.create(db_session=async_session, obj_in=vault_obj)


@pytest_asyncio.fixture(name="room")
async def room_fixture(async_session: AsyncSession, vault: Vault, room_data: dict) -> Room:
    room_obj = RoomCreate(**room_data | {"vault_id": vault.id})
    return await crud.room.create(db_session=async_session, obj_in=room_obj)


@pytest_asyncio.fixture(name="dweller")
async def dweller_fixture(async_session: AsyncSession, vault: Vault, dweller_data: dict) -> Dweller:
    dweller_obj = Dweller(**dweller_data | {"vault_id": vault.id})
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_obj)
