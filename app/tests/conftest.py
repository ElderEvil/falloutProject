import asyncio
from collections.abc import Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app import crud
from app.core.config import settings
from app.db.session import get_async_session
from app.schemas.user import UserCreate
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers
from main import app


@pytest.fixture(scope="session")
def event_loop(request) -> Generator:  # noqa: ANN001
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_connection():
    async_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    async with async_engine.connect() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.commit()
        yield conn
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.commit()

    await async_engine.dispose()


@pytest_asyncio.fixture(scope="function")
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
async def async_client(async_session: AsyncSession, superuser: None) -> Generator[AsyncClient]:
    app.dependency_overrides[get_async_session] = lambda: async_session

    async with AsyncClient(
        app=app,
        base_url=f"https://{settings.API_V1_STR}",
    ) as client:
        yield client


@pytest.fixture()
async def superuser_token_headers(async_client: AsyncClient) -> dict[str, str]:
    return await get_superuser_token_headers(async_client)


@pytest.fixture()
async def normal_user_token_headers(async_client: AsyncClient, async_session: AsyncSession) -> dict[str, str]:
    return await authentication_token_from_email(
        client=async_client,
        email=settings.EMAIL_TEST_USER,
        db_session=async_session,
    )
