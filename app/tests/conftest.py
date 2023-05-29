import asyncio
from collections.abc import Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_superuser_token_headers
from main import app


@pytest.fixture(scope="session")
def event_loop(request) -> Generator:  # noqa: ANN001
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def async_engine():
    a_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=True, poolclass=StaticPool)
    yield a_engine
    a_engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def session() -> AsyncSession:
    # a_engine = create_async_engine(
    #     "sqlite+aiosqlite:///:memory:",
    #     echo=True,
    #     poolclass=StaticPool
    # )
    with async_engine() as ae:
        created_session = sessionmaker(bind=ae, class_=AsyncSession, expire_on_commit=False)
        async with created_session() as a_session:
            async with ae.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)

            yield a_session

        async with ae.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

        # await async_engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def client():
    async with AsyncClient(app=app, base_url=f"https://{settings.API_V1_STR}") as a_client:
        yield a_client


@pytest.fixture(scope="module")
async def superuser_token_headers(client: AsyncClient, session: AsyncSession) -> dict[str, str]:
    return await get_superuser_token_headers(client)


@pytest.fixture(scope="module")
async def normal_user_token_headers(client: AsyncClient, session: AsyncSession) -> dict[str, str]:
    return await authentication_token_from_email(
        client=client,
        email=settings.EMAIL_TEST_USER,
        db=session,
    )
