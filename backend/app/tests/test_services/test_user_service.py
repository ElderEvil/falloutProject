"""Registration owns a single transaction boundary (real session; no CRUD doubles).

SERVICE_LAYER.md "Transaction ownership": the service entry point commits once and
CRUD stages rows with ``flush``. These tests pin the observable contract on the test
database: one durable user+profile write on success, and no surviving rows when a
later write in the same operation fails.
"""

from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Redis
from sqlalchemy import event, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.user_profile import profile_crud
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate, UserWithTokens
from app.services.user_service import user_service
from app.tests.factory.users import create_fake_user

FaultHook = Callable[[str], object]


@asynccontextmanager
async def _fail_sql(async_session: AsyncSession, predicate: FaultHook, message: str) -> AsyncGenerator[None]:
    """Raise at the first statement matching ``predicate`` while the block runs."""
    connection = (await async_session.connection()).sync_connection

    def hook(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        if predicate(statement):
            raise RuntimeError(message)

    event.listen(connection, "before_cursor_execute", hook)
    try:
        yield
    finally:
        event.remove(connection, "before_cursor_execute", hook)


def _inserts_profile(statement: str) -> bool:
    return statement.lower().startswith("insert into userprofile")


def _updates_user(statement: str) -> bool:
    return statement.lower().startswith("update user ")


async def _register(async_session: AsyncSession, redis_client: Redis, data: dict[str, str]) -> UserWithTokens:
    return await user_service.register_user(
        db_session=async_session,
        redis_client=redis_client,
        username=data["username"],
        password=data["password"],
        email=data["email"],
    )


async def test_registration_commits_once_and_creates_user_with_profile(
    async_session: AsyncSession, _shared_fake_redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = create_fake_user()
    commits: list[int] = []
    original_commit = async_session.commit

    async def counting_commit() -> None:
        commits.append(1)
        await original_commit()

    monkeypatch.setattr(async_session, "commit", counting_commit)
    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock) as send_email:
        result = await _register(async_session, _shared_fake_redis, data)

    assert len(commits) == 1, f"registration committed {len(commits)} times; the service owns exactly one"
    user = await crud.user.get_by_email(async_session, email=data["email"])
    assert user is not None
    assert result.id == user.id
    assert user.email_verification_token is not None
    profiles = (await async_session.execute(select(UserProfile).where(UserProfile.user_id == user.id))).scalars().all()
    assert len(profiles) == 1
    send_email.assert_awaited_once()


async def test_failure_at_profile_write_leaves_no_user(async_session: AsyncSession, _shared_fake_redis: Redis) -> None:
    data = create_fake_user()
    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock) as send_email:
        async with _fail_sql(async_session, _inserts_profile, "injected profile write failure"):
            with pytest.raises(RuntimeError, match="injected profile write failure"):
                await _register(async_session, _shared_fake_redis, data)

    await async_session.rollback()
    assert await crud.user.get_by_email(async_session, email=data["email"]) is None
    assert (await async_session.execute(select(UserProfile))).scalars().all() == []
    send_email.assert_not_awaited()


async def test_failure_after_the_first_durable_write_leaves_no_user(
    async_session: AsyncSession, _shared_fake_redis: Redis
) -> None:
    """The verification-token write used to land after ``crud.user.create`` committed."""
    data = create_fake_user()
    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock) as send_email:
        async with _fail_sql(async_session, _updates_user, "injected token write failure"):
            with pytest.raises(RuntimeError, match="injected token write failure"):
                await _register(async_session, _shared_fake_redis, data)

    await async_session.rollback()
    assert await crud.user.get_by_email(async_session, email=data["email"]) is None, (
        "a failed registration must not leave a user row behind"
    )
    assert (await async_session.execute(select(UserProfile))).scalars().all() == []
    send_email.assert_not_awaited()


async def test_profile_creation_stays_race_safe(async_session: AsyncSession) -> None:
    """A second create for the same user returns the winner instead of raising."""
    user = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))
    user_id = user.id
    profile = await profile_crud.get_by_user_id(async_session, user_id)
    assert profile is not None
    await async_session.delete(profile)
    await async_session.commit()

    first = await profile_crud.create_for_user(async_session, user_id)
    second = await profile_crud.create_for_user(async_session, user_id)
    assert second.id == first.id
    await async_session.commit()
    persisted = (await async_session.execute(select(UserProfile).where(UserProfile.user_id == user_id))).scalars().all()
    assert len(persisted) == 1


async def test_get_or_create_profile_creates_once_at_the_service_boundary(
    async_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lazy profile path used by GET /users/me/profile commits in the service, once."""
    user = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()), commit=False)
    user_id = user.id
    await async_session.commit()
    assert await profile_crud.get_by_user_id(async_session, user_id) is None

    commits: list[int] = []
    original_commit = async_session.commit

    async def counting_commit() -> None:
        commits.append(1)
        await original_commit()

    monkeypatch.setattr(async_session, "commit", counting_commit)
    first = await user_service.get_or_create_profile(async_session, user_id)
    second = await user_service.get_or_create_profile(async_session, user_id)

    assert second.id == first.id
    assert len(commits) == 1
