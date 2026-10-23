"""Real row locks prevent two administrators from deleting one another concurrently."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import delete
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


def test_concurrent_admin_deletion_keeps_an_active_superuser() -> None:
    asyncio.run(_concurrent_deletion())


async def _concurrent_deletion() -> None:
    engine = create_async_engine(str(settings.ASYNC_DATABASE_URI), pool_size=2, max_overflow=0)
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
                    perform_support_action(first, "user", "soft-delete", ids[1], actor_id=str(ids[0])),
                    perform_support_action(second, "user", "soft-delete", ids[0], actor_id=str(ids[1])),
                    return_exceptions=True,
                ),
                timeout=15,
            )
            assert sum(result is None for result in results) == 1, results
            assert sum(isinstance(result, AccessDeniedException) for result in results) == 1, results
        async with maker() as session:
            users = (await session.execute(select(User).where(col(User.id).in_(ids)))).scalars().all()
            assert sum(user.is_active and user.is_superuser and not user.is_deleted for user in users) == 1
    finally:
        async with maker() as session:
            await session.execute(delete(UserProfile).where(col(UserProfile.user_id).in_(ids)))
            await session.execute(delete(User).where(col(User.id).in_(ids)))
            await session.commit()
        await engine.dispose()
