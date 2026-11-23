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
from app.utils.exceptions import OAuthFlowError, ResourceConflictException

pytestmark = pytest.mark.integration
SERVICE = OAuthService()


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
    created: list = []
    try:
        async with maker() as first, maker() as second:
            try:
                yield first, second, created
            finally:
                # Mirror the request lifecycle: the racing session never commits.
                await second.rollback()
                for user_id in created:
                    await _cleanup(first, user_id)
    finally:
        await engine.dispose()


async def _verified_user(session: AsyncSession, created: list) -> User:
    suffix = uuid4().hex[:8]
    user = await crud.user.create(
        session,
        obj_in=UserCreate(username=f"oauthpg{suffix}", email=f"oauthpg{suffix}@example.com", password="Secret123!"),
    )
    user.email_verified = True
    await session.commit()
    created.append(user.id)
    return user


async def _links(session: AsyncSession, user_id) -> list[OAuthAccount]:
    return (await session.execute(select(OAuthAccount).where(OAuthAccount.user_id == user_id))).scalars().all()


async def _cleanup(session: AsyncSession, user_id) -> None:
    await session.rollback()
    for model in (OAuthAccount, UserProfile):
        await session.execute(delete(model).where(model.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()


async def _overlapping_same_identity() -> None:
    async with _sessions() as (first, second, created):
        user = await _verified_user(first, created)
        profile = {"provider_user_id": "same-subject", "email": user.email, "login": "octo"}
        results = await asyncio.gather(
            SERVICE._link_existing(first, OAuthProviderEnum.GITHUB, profile, user),
            SERVICE._link_existing(second, OAuthProviderEnum.GITHUB, profile, user),
        )
        assert all(result is not None and result.id == user.id for result in results)
        assert len(await _links(first, user.id)) == 1


async def _email_change_race() -> None:
    async with _sessions() as (first, second, created):
        user = await _verified_user(first, created)
        profile = {"provider_user_id": "late-subject", "email": user.email, "login": "octo"}
        async with first.begin():
            locked = await crud.user.get_for_update(first, user.id)
            assert locked is not None
            locked.email = f"changed{uuid4().hex[:8]}@example.com"
            pending = asyncio.create_task(SERVICE._link_existing(second, OAuthProviderEnum.GITHUB, profile, user))
            await asyncio.sleep(0.3)
        assert await pending is None
        assert await _links(first, user.id) == []


async def _different_identity_rejected() -> None:
    async with _sessions() as (first, second, created):
        user = await _verified_user(first, created)
        await SERVICE._link_existing(
            first,
            OAuthProviderEnum.GITHUB,
            {"provider_user_id": "first-subject", "email": user.email, "login": "octo"},
            user,
        )
        with pytest.raises(OAuthFlowError) as exc:
            await SERVICE._link_existing(
                second,
                OAuthProviderEnum.GITHUB,
                {"provider_user_id": "other-subject", "email": user.email, "login": "other"},
                user,
            )
        assert exc.value.code == "provider_already_linked"


async def _creation_conflict_rolls_back() -> None:
    async with _sessions() as (first, second, created):
        email = f"rollback{uuid4().hex[:8]}@example.com"
        user, _ = await crud.user.create_with_oauth_account(
            first,
            provider="github",
            provider_user_id="duplicate-subject",
            username=f"rollback{uuid4().hex[:8]}",
            email=email,
        )
        second_email = f"other{uuid4().hex[:8]}@example.com"
        created.append(user.id)
        with pytest.raises(ResourceConflictException):
            await crud.user.create_with_oauth_account(
                second,
                provider="github",
                provider_user_id="duplicate-subject",
                username=f"other{uuid4().hex[:8]}",
                email=second_email,
            )
        await second.rollback()
        leftover = (await first.execute(select(User).where(User.email == second_email))).scalars().all()
        linked = (
            (await first.execute(select(OAuthAccount).where(OAuthAccount.provider_user_id == "duplicate-subject")))
            .scalars()
            .all()
        )
        assert leftover == []
        assert len(linked) == 1


def test_overlapping_same_identity_returns_linked_user():
    asyncio.run(_overlapping_same_identity())


def test_email_change_during_link_writes_nothing():
    asyncio.run(_email_change_race())


def test_different_identity_is_rejected():
    asyncio.run(_different_identity_rejected())


def test_creation_conflict_rolls_back():
    asyncio.run(_creation_conflict_rolls_back())
