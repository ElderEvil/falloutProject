import asyncio
from collections.abc import Generator

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

from app import crud
from app.core.config import settings
from app.db.session import get_async_session
from app.schemas.user import UserCreate
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers
from main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_connection() -> AsyncConnection:
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True, poolclass=StaticPool)

    @event.listens_for(SQLModel.metadata, "before_create")
    def _replace_jsonb_with_json(target, connection, **kw):  # noqa: ARG001
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()

    async with async_engine.connect() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.commit()
        yield conn
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.commit()

    await async_engine.dispose()


@pytest_asyncio.fixture
async def async_session(db_connection: AsyncConnection) -> AsyncSession:
    session = sessionmaker(
        bind=db_connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session() as s:
        s.commit = s.flush
        yield s
        await s.rollback()


@pytest_asyncio.fixture(name="superuser", scope="function")
async def _superuser(async_session: AsyncSession):
    user_in = UserCreate(
        username=settings.FIRST_SUPERUSER_EMAIL,
        email=settings.FIRST_SUPERUSER_EMAIL,
        password=settings.FIRST_SUPERUSER_PASSWORD,
        is_superuser=True,
    )
    await crud.user.create(db_session=async_session, obj_in=user_in)


@pytest_asyncio.fixture(scope="function")
async def async_client(async_session: AsyncSession, superuser: None) -> Generator[AsyncClient]:  # noqa: ARG001
    app.dependency_overrides[get_async_session] = lambda: async_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url=f"https://{settings.API_V1_STR}",
    ) as client:
        yield client


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
    import random  # noqa: PLC0415

    return {
        "number": random.randint(1, 1_000),
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
        "power": random.randint(0, 100),
        "food": random.randint(0, 100),
        "water": random.randint(0, 100),
    }


@pytest.fixture(name="dweller_data")
def dweller_data_fixture():
    import random  # noqa: PLC0415

    from faker import Faker  # noqa: PLC0415

    from app.schemas.common import GenderEnum, RarityEnum  # noqa: PLC0415
    from app.tests.utils.utils import get_gender_based_name, get_stats_by_rarity  # noqa: PLC0415

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
    import random  # noqa: PLC0415

    from faker import Faker  # noqa: PLC0415

    from app.schemas.user import UserCreate  # noqa: PLC0415
    from app.schemas.vault import VaultCreateWithUserID  # noqa: PLC0415

    fake = Faker()

    # Create user first
    user_in = UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password())
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    # Create vault
    vault_data = {
        "number": random.randint(1, 1_000),
        "bottle_caps": random.randint(100, 1_000_000),
        "happiness": random.randint(0, 100),
        "power": random.randint(0, 100),
        "food": random.randint(0, 100),
        "water": random.randint(0, 100),
    }
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    return await crud.vault.create(db_session=async_session, obj_in=vault_in)


@pytest_asyncio.fixture(name="dweller")
async def dweller_fixture(async_session: AsyncSession, vault: "Vault", dweller_data: dict) -> "Dweller":  # noqa: F821
    from app.schemas.dweller import DwellerCreate  # noqa: PLC0415

    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
