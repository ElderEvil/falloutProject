"""PostgreSQL concurrency coverage for provider linking.

Each test owns one event loop via ``asyncio.run`` so the asyncpg pool is never
shared across pytest-asyncio's fixture/test loops.
"""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import OAuthProviderEnum
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate
from app.services.oauth_service import OAuthService
from app.utils.exceptions import OAuthFlowError

pytestmark = pytest.mark.integration


@asynccontextmanager
async def _sessions():
    engine = create_async_engine(str(settings.ASYNC_DATABASE_URI), pool_size=5, max_overflow=5)
    # Schema comes from Alembic; never create_all on the shared database.
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # pragma: no cover - environment guard
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as first, maker() as second:
            yield first, second
    finally:
        await engine.dispose()


async def _verified_user(session: AsyncSession) -> User:
    user = await crud.user.create(
        session,
        obj_in=UserCreate(
            username=f"oauthpg{uuid4().hex[:8]}",
            email=f"oauthpg{uuid4().hex[:8]}@example.com",
            password="Secret123!",
        ),
    )
    user.email_verified = True
    await session.commit()
    return user


async def _cleanup(session: AsyncSession, user_id) -> None:
    await session.rollback()
    await session.execute(delete(OAuthAccount).where(OAuthAccount.user_id == user_id))
    await session.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


async def _overlapping_same_identity() -> None:
    service = OAuthService()
    async with _sessions() as (first, second):
        user = await _verified_user(first)
        profile = {"provider_user_id": "same-subject", "email": user.email, "login": "octo"}
        try:
            results = await asyncio.gather(
                service._link_existing(first, OAuthProviderEnum.GITHUB, profile, user),
                service._link_existing(second, OAuthProviderEnum.GITHUB, profile, user),
            )
            assert all(result is not None and result.id == user.id for result in results)
            links = (
                await first.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
            ).scalars().all()
            assert len(links) == 1
        finally:
            await second.rollback()
            await _cleanup(first, user.id)


async def _email_change_race() -> None:
    service = OAuthService()
    async with _sessions() as (first, second):
        user = await _verified_user(first)
        profile = {"provider_user_id": "late-subject", "email": user.email, "login": "octo"}
        try:
            async with first.begin():
                locked = await crud.user.get_for_update(first, user.id)
                assert locked is not None
                locked.email = f"changed{uuid4().hex[:8]}@example.com"
                pending = asyncio.create_task(
                    service._link_existing(second, OAuthProviderEnum.GITHUB, profile, user)
                )
                await asyncio.sleep(0.3)

            assert await pending is None
            links = (
                await first.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id))
            ).scalars().all()
            assert links == []
        finally:
            await second.rollback()
            await _cleanup(first, user.id)


async def _different_identity_rejected() -> None:
    service = OAuthService()
    async with _sessions() as (first, second):
        user = await _verified_user(first)
        await service._link_existing(
            first,
            OAuthProviderEnum.GITHUB,
            {"provider_user_id": "first-subject", "email": user.email, "login": "octo"},
            user,
        )
        try:
            with pytest.raises(OAuthFlowError) as exc:
                await service._link_existing(
                    second,
                    OAuthProviderEnum.GITHUB,
                    {"provider_user_id": "other-subject", "email": user.email, "login": "other"},
                    user,
                )
            assert exc.value.code == "provider_already_linked"
        finally:
            await second.rollback()
            await _cleanup(first, user.id)


def test_overlapping_same_identity_returns_linked_user():
    asyncio.run(_overlapping_same_identity())


def test_email_change_during_link_writes_nothing():
    asyncio.run(_email_change_race())


def test_different_identity_is_rejected():
    asyncio.run(_different_identity_rejected())
