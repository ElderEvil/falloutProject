import asyncio
from collections.abc import AsyncGenerator, Generator
from contextlib import suppress
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

# Global engine reference for database cleanup across fixtures
_test_async_engine = None

from app.core.config import settings  # noqa: E402

# Disable rate limiting for tests before importing main
settings.ENABLE_RATE_LIMITING = False

# Mock storage service before importing main
with patch("app.services.storage.factory.create_storage_service") as mock_storage:
    mock_instance = MagicMock()
    mock_instance.enabled = False  # Disable storage for tests by default
    mock_storage.return_value = mock_instance
    from main import app

from app import crud  # noqa: E402
from app.db.session import get_async_session  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.tests.utils.user import authentication_token_from_email  # noqa: E402
from app.tests.utils.utils import get_superuser_token_headers  # noqa: E402


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_connection() -> AsyncConnection:
    global _test_async_engine  # noqa: PLW0603
    _test_async_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", echo=False, future=True, poolclass=StaticPool
    )

    @event.listens_for(SQLModel.metadata, "before_create")
    def _replace_jsonb_with_json(target, connection, **kw):
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()

    async with _test_async_engine.connect() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.commit()
        yield conn
        # Clean up after all tests in session
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.commit()

    await _test_async_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(db_connection: AsyncConnection) -> AsyncSession:
    session = sessionmaker(
        bind=db_connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with session() as s:
        yield s
        # Rollback any uncommitted changes
        with suppress(Exception):
            await s.rollback()
        # Close the session to release connections
        with suppress(Exception):
            await s.close()

    # Clean up the database after each test function
    async with _test_async_engine.connect() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.commit()


@pytest_asyncio.fixture(name="superuser", scope="function")
async def _superuser(async_session: AsyncSession):
    # Check if superuser already exists to avoid integrity errors on repeated fixture usage
    existing_user = await crud.user.get_by_email(
        email=settings.FIRST_SUPERUSER_EMAIL,
        db_session=async_session,
    )
    if existing_user is not None:
        return existing_user

    user_in = UserCreate(
        username=settings.FIRST_SUPERUSER_EMAIL,
        email=settings.FIRST_SUPERUSER_EMAIL,
        password=settings.FIRST_SUPERUSER_PASSWORD,
        is_superuser=True,
    )
    return await crud.user.create(db_session=async_session, obj_in=user_in)


@pytest_asyncio.fixture(scope="function")
async def async_client(async_session: AsyncSession, superuser: Any) -> AsyncGenerator[AsyncClient]:
    app.dependency_overrides[get_async_session] = lambda: async_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url=f"https://{settings.API_V1_STR}",
        ) as client:
            yield client
    finally:
        # Clean up dependency overrides to avoid affecting other tests
        app.dependency_overrides.pop(get_async_session, None)


@pytest_asyncio.fixture
async def superuser_token_headers(async_client: AsyncClient) -> dict[str, str]:
    return await get_superuser_token_headers(async_client)


@pytest_asyncio.fixture
async def normal_user_token_headers(async_client: AsyncClient, async_session: AsyncSession) -> dict[str, str]:
    return await authentication_token_from_email(
        client=async_client,
        email=settings.EMAIL_TEST_USER,
        db_session=async_session,
    )


# Common fixtures for tests
@pytest.fixture(name="vault_data")
def vault_data_fixture():
    import random

    return {
        "number": random.randint(1, 999),  # Must be < 1000 per validation
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
        "power": random.randint(0, 100),
        "food": random.randint(0, 100),
        "water": random.randint(0, 100),
    }


@pytest.fixture(name="dweller_data")
def dweller_data_fixture():
    import random

    from faker import Faker

    from app.schemas.common import GenderEnum, RarityEnum
    from app.tests.utils.utils import get_gender_based_name, get_stats_by_rarity

    fake = Faker()
    gender = random.choice(list(GenderEnum))
    rarity = random.choice(list(RarityEnum))
    stats = get_stats_by_rarity(rarity)

    max_health = random.randint(50, 1_000)
    health = random.randint(0, max_health)
    radiation = random.randint(0, 1_000)

    return stats | {
        "first_name": get_gender_based_name(gender),
        "last_name": fake.last_name(),
        "is_adult": random.choice([True, False]),
        "gender": gender,
        "rarity": rarity.value,
        "level": random.randint(1, 50),
        "experience": random.randint(0, 1_000),
        "max_health": max_health,
        "health": health,
        "radiation": radiation,
        "happiness": random.randint(10, 100),
        "stimpack": random.randint(0, 15),
        "radaway": random.randint(0, 15),
    }


@pytest_asyncio.fixture(name="vault")
async def vault_fixture(async_session: AsyncSession) -> "Vault":  # noqa: F821
    import random

    from faker import Faker

    from app.schemas.user import UserCreate
    from app.schemas.vault import VaultCreateWithUserID

    fake = Faker()

    # Create user first
    user_in = UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password())
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    # Create vault
    vault_data = {
        "number": random.randint(1, 999),  # Must be < 1000 per validation
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
        "power": random.randint(0, 100),
        "food": random.randint(0, 100),
        "water": random.randint(0, 100),
        "population_max": 50,  # Set population max to allow dwellers
    }
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    return await crud.vault.create(db_session=async_session, obj_in=vault_in)


@pytest_asyncio.fixture(name="dweller")
async def dweller_fixture(async_session: AsyncSession, vault: "Vault", dweller_data: dict) -> "Dweller":  # noqa: F821
    from app.schemas.dweller import DwellerCreate

    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="radio_room")
async def radio_room_fixture(async_session: AsyncSession, vault: "Vault") -> "Room":  # noqa: F821
    """Create a radio room for testing."""
    from app.schemas.common import RoomTypeEnum, SPECIALEnum
    from app.schemas.room import RoomCreate

    room_data = {
        "name": "Radio Studio",
        "category": RoomTypeEnum.MISC,
        "ability": SPECIALEnum.CHARISMA,
        "population_required": None,
        "base_cost": 100,
        "incremental_cost": 50,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "capacity": 2,
        "output": None,
        "size_min": 1,
        "size_max": 3,
        "size": 2,
        "tier": 1,
        "coordinate_x": 0,
        "coordinate_y": 0,
        "image_url": None,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    return await crud.room.create(db_session=async_session, obj_in=room_in)


@pytest_asyncio.fixture(name="radio_dweller")
async def radio_dweller_fixture(async_session: AsyncSession, vault: "Vault", radio_room: "Room") -> "Dweller":  # noqa: F821
    """Create a dweller with high charisma for radio room."""
    from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
    from app.schemas.dweller import DwellerCreate

    dweller_data = {
        "first_name": "DJ",
        "last_name": "Radio",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 5,
        "experience": 100,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 80,
        "room_id": radio_room.id,
        "strength": 3,
        "perception": 4,
        "endurance": 4,
        "charisma": 10,
        "intelligence": 5,
        "agility": 4,
        "luck": 5,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


# Notification test fixtures
@pytest_asyncio.fixture
async def user_with_vault(async_session: AsyncSession) -> tuple["User", "Vault"]:  # noqa: F821
    """Create a user with a vault for notification testing."""
    from app.schemas.user import UserCreate
    from app.schemas.vault import VaultCreate

    # Create user
    user_data = UserCreate(
        username="test_user",
        email="test@example.com",
        password="testpass123",
    )
    user = await crud.user.create(db_session=async_session, obj_in=user_data)

    # Create vault
    vault_data = VaultCreate(number=101, name="Test Vault")
    vault = await crud.vault.create_with_user_id(db_session=async_session, obj_in=vault_data, user_id=user.id)

    return user, vault


@pytest_asyncio.fixture
async def dweller_in_vault(async_session: AsyncSession, user_with_vault: tuple) -> "Dweller":  # noqa: F821
    """Create a dweller in the test vault."""
    from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
    from app.schemas.dweller import DwellerCreate

    _, vault = user_with_vault

    dweller_data = DwellerCreate(
        vault_id=vault.id,
        first_name="Test",
        last_name="Dweller",
        gender=GenderEnum.MALE,
        age_group=AgeGroupEnum.ADULT,
        level=5,
        experience=0,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
        rarity=RarityEnum.COMMON,
    )
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_data)


@pytest_asyncio.fixture
async def room_in_vault(async_session: AsyncSession, user_with_vault: tuple) -> "Room":  # noqa: F821
    """Create a room in the test vault."""
    from app.schemas.common import RoomTypeEnum, SPECIALEnum
    from app.schemas.room import RoomCreate

    _, vault = user_with_vault

    room_data = RoomCreate(
        vault_id=vault.id,
        name="Test Room",
        category=RoomTypeEnum.PRODUCTION,
        ability=SPECIALEnum.STRENGTH,
        base_cost=100,
        incremental_cost=50,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        capacity=4,
        output=100,
        size_min=1,
        size_max=3,
        size=2,
        tier=1,
        coordinate_x=1,
        coordinate_y=1,
    )
    return await crud.room.create(db_session=async_session, obj_in=room_data)


@pytest_asyncio.fixture(name="vault_with_rooms")
async def vault_with_rooms_fixture(
    async_session: AsyncSession,
    vault: "Vault",  # noqa: F821
) -> tuple["Vault", list["Room"]]:  # noqa: F821
    """
    Vault with 3 rooms of different types.

    Returns:
        Tuple of (vault, [power_generator, water_treatment, diner])

    Usage:
        async def test_something(vault_with_rooms):
            vault, rooms = vault_with_rooms
            assert len(rooms) == 3
    """
    from app.schemas.room import RoomCreate

    room_configs = [
        {"name": "Power Generator", "level": 1, "tier": 1},
        {"name": "Water Treatment", "level": 1, "tier": 1},
        {"name": "Diner", "level": 1, "tier": 1},
    ]

    rooms = []
    for config in room_configs:
        room_in = RoomCreate(**config, vault_id=vault.id)
        room = await crud.room.create(db_session=async_session, obj_in=room_in)
        rooms.append(room)

    return vault, rooms


@pytest_asyncio.fixture(name="room_with_dwellers")
async def room_with_dwellers_fixture(
    async_session: AsyncSession,
) -> dict:
    """
    Room with 2 dwellers assigned (creates its own vault).

    Returns:
        Dict with 'room', 'dwellers', and 'vault' keys

    Usage:
        async def test_room_capacity(room_with_dwellers):
            room = room_with_dwellers["room"]
            dwellers = room_with_dwellers["dwellers"]
            assert len(dwellers) == 2
    """
    import random

    from faker import Faker

    from app.schemas.common import RoomTypeEnum
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate
    from app.schemas.vault import VaultCreateWithUserID
    from app.tests.factory.dwellers import create_random_common_dweller

    fake = Faker()

    user_in = UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password())
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    vault_in = VaultCreateWithUserID(
        number=random.randint(1, 999),
        bottle_caps=1000,
        population_max=50,  # Set population max to allow dwellers
        user_id=user.id,
    )
    vault = await crud.vault.create(db_session=async_session, obj_in=vault_in)

    room_in = RoomCreate(
        name="Power Generator",
        category=RoomTypeEnum.PRODUCTION,
        ability=None,
        population_required=None,
        base_cost=100,
        incremental_cost=None,
        t2_upgrade_cost=None,
        t3_upgrade_cost=None,
        size_min=1,
        size_max=3,
        tier=1,
        vault_id=vault.id,
    )
    room = await crud.room.create(db_session=async_session, obj_in=room_in)

    dwellers = []
    for _ in range(2):
        dweller_data = create_random_common_dweller()
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
        # Assign dweller to room using move_to_room (room_id not supported in DwellerCreate)
        await crud.dweller.move_to_room(async_session, dweller.id, room.id)
        # Get the actual Dweller model with weapon relationship loaded
        dweller = await crud.dweller.get(async_session, dweller.id)
        dwellers.append(dweller)

    # Commit to ensure dwellers are visible to subsequent queries
    await async_session.commit()
    await async_session.refresh(room)

    return {"room": room, "dwellers": dwellers, "vault": vault}


@pytest_asyncio.fixture(name="equipped_dweller")
async def equipped_dweller_fixture(
    async_session: AsyncSession,
    dweller: "Dweller",  # noqa: F821
) -> tuple["Dweller", "Outfit", "Weapon"]:  # noqa: F821
    """
    Dweller with outfit and weapon equipped.

    Returns:
        Tuple of (dweller, outfit, weapon)

    Usage:
        async def test_combat_power(equipped_dweller):
            dweller, outfit, weapon = equipped_dweller
    """
    from app.tests.factory.items import create_fake_outfit, create_fake_weapon

    outfit_data = create_fake_outfit()
    outfit_data["dweller_id"] = dweller.id
    outfit = await crud.outfit.create(db_session=async_session, obj_in=outfit_data)

    weapon_data = create_fake_weapon()
    weapon_data["dweller_id"] = dweller.id
    weapon = await crud.weapon.create(db_session=async_session, obj_in=weapon_data)

    return dweller, outfit, weapon


@pytest_asyncio.fixture(name="populated_vault")
async def populated_vault_fixture(
    async_session: AsyncSession,
) -> tuple["Vault", list["Room"], list["Dweller"]]:  # noqa: F821
    """
    Fully populated vault: 3 rooms, each with 2 dwellers (6 total).

    Returns:
        Tuple of (vault, rooms, dwellers)

    Usage:
        async def test_game_loop(populated_vault):
            vault, rooms, dwellers = populated_vault
            assert len(rooms) == 3
            assert len(dwellers) == 6
    """
    import random

    from faker import Faker

    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate
    from app.schemas.vault import VaultCreateWithUserID
    from app.tests.factory.dwellers import create_random_common_dweller

    fake = Faker()

    user_in = UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password())
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    vault_in = VaultCreateWithUserID(
        number=random.randint(1, 999),
        bottle_caps=1000,
        population_max=50,  # Set population max to allow dwellers
        user_id=user.id,
    )
    vault = await crud.vault.create(db_session=async_session, obj_in=vault_in)

    room_configs = [
        {"name": "Power Generator", "level": 1, "tier": 1},
        {"name": "Water Treatment", "level": 1, "tier": 1},
        {"name": "Diner", "level": 1, "tier": 1},
    ]

    rooms = []
    dwellers = []

    for config in room_configs:
        room_in = RoomCreate(**config, vault_id=vault.id)
        room = await crud.room.create(db_session=async_session, obj_in=room_in)
        rooms.append(room)

        for _ in range(2):
            dweller_data = create_random_common_dweller()
            dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
            dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
            # Assign dweller to room using move_to_room (room_id not supported in DwellerCreate)
            await crud.dweller.move_to_room(async_session, dweller.id, room.id)
            # Get the actual Dweller model with weapon relationship loaded
            dweller = await crud.dweller.get(async_session, dweller.id)
            dwellers.append(dweller)

        # Commit to ensure dwellers are visible and room relationships are updated
        await async_session.commit()
        await async_session.refresh(room)

    return vault, rooms, dwellers


@pytest_asyncio.fixture(name="vault_with_resources")
async def vault_with_resources_fixture(
    async_session: AsyncSession,
    vault: "Vault",  # noqa: F821
) -> "Vault":  # noqa: F821
    """
    Vault with abundant resources for testing economy/building.

    Returns:
        Vault with 10000 caps, 100 power/food/water

    Usage:
        async def test_expensive_build(vault_with_resources):
            assert vault_with_resources.bottle_caps == 10000
    """
    vault.bottle_caps = 10000
    vault.power = 100
    vault.food = 100
    vault.water = 100
    async_session.add(vault)
    await async_session.flush()
    await async_session.refresh(vault)
    return vault
