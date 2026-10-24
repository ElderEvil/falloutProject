"""Concurrent secondary administrators cannot remove each other or the first account."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate
from app.services.admin_service import perform_support_action
from app.utils.exceptions import AccessDeniedException

pytestmark = pytest.mark.integration


def test_secondary_admins_cannot_delete_one_another_concurrently() -> None:
    database_uri = os.getenv("ADMIN_TEST_DATABASE_URI")
    if not database_uri:
        pytest.skip("Set ADMIN_TEST_DATABASE_URI to a dedicated, migrated PostgreSQL test database")
    url = make_url(database_uri)
    if url.drivername != "postgresql+asyncpg" or not url.database:
        pytest.fail("ADMIN_TEST_DATABASE_URI must use postgresql+asyncpg and name a test database")
    if url.database == make_url(str(settings.ASYNC_DATABASE_URI)).database:
        pytest.fail("ADMIN_TEST_DATABASE_URI must name a different database from the application")
    asyncio.run(_concurrent_deletion(database_uri))


async def _concurrent_deletion(database_uri: str) -> None:
    engine = create_async_engine(database_uri, pool_size=2, max_overflow=0)
    try:
        async with engine.connect() as connection:
            await connection.execute(select(1))
    except Exception:  # pragma: no cover - optional local PostgreSQL
        await engine.dispose()
        pytest.skip("PostgreSQL unavailable")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    ids = []
    try:
        async with maker() as session:
            for _ in range(2):
                suffix = uuid4().hex[:12]
                user = await crud.user.create(
                    session,
                    UserCreate(
                        username=f"adminpg{suffix}", email=f"adminpg{suffix}@example.com", password="Secret123!"
                    ),
                )
                ids.append(user.id)
                user.is_superuser = True
                await session.commit()
        async with maker() as first, maker() as second:
            # Both sessions cache an active actor before the competing transaction.
            actors = await asyncio.gather(crud.user.get(first, ids[0]), crud.user.get(second, ids[1]))
            assert all(actor.is_active and actor.is_superuser for actor in actors)
            results = await asyncio.wait_for(
                asyncio.gather(
                    _attempt_deletion(first, ids[1], ids[0]),
                    _attempt_deletion(second, ids[0], ids[1]),
                    return_exceptions=True,
                ),
                timeout=15,
            )
            assert all(isinstance(result, AccessDeniedException) for result in results), results
        async with maker() as session:
            users = (await session.execute(select(User).where(col(User.id).in_(ids)))).scalars().all()
            assert len(users) == 2
            assert all(user.is_active and user.is_superuser and not user.is_deleted for user in users)
    finally:
        async with maker() as session:
            await session.execute(delete(UserProfile).where(col(UserProfile.user_id).in_(ids)))
            await session.execute(delete(User).where(col(User.id).in_(ids)))
            await session.commit()
        await engine.dispose()


async def _attempt_deletion(session: AsyncSession, target_id, actor_id) -> None:
    try:
        await perform_support_action(session, "user", "soft-delete", target_id, actor_id=str(actor_id))
    finally:
        # Each HTTP request closes its transaction even when authorization fails.
        await session.rollback()


@pytest.mark.parametrize("database", [None, "application", "sqlite"])
def test_admin_concurrency_requires_a_dedicated_database(monkeypatch: pytest.MonkeyPatch, database: str | None) -> None:
    if database is None:
        monkeypatch.delenv("ADMIN_TEST_DATABASE_URI", raising=False)
        with pytest.raises(pytest.skip.Exception, match="dedicated"):
            test_secondary_admins_cannot_delete_one_another_concurrently()
    else:
        uri = str(settings.ASYNC_DATABASE_URI) if database == "application" else "sqlite+aiosqlite:///:memory:"
        monkeypatch.setenv("ADMIN_TEST_DATABASE_URI", uri)
        with pytest.raises(pytest.fail.Exception, match=r"different database|postgresql"):
            test_secondary_admins_cannot_delete_one_another_concurrently()
