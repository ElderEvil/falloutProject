"""Registration owns a single transaction boundary (real session; no CRUD doubles).

The service commits once; a failure at a later write leaves no user and no profile.
"""

from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.user_profile import profile_crud
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate, UserWithTokens
from app.schemas.user_profile import ProfileUpdate
from app.services.user_service import user_service
from app.tests.factory.users import create_fake_user
from app.tests.test_services._transaction_helpers import counting_commit, fail_sql


def _inserts_profile(statement: str) -> bool:
    return statement.lower().startswith("insert into userprofile")


def _updates_user(statement: str) -> bool:
    return statement.lower().startswith("update user ")


def _updates_profile(statement: str) -> bool:
    return statement.lower().startswith("update userprofile")


async def _register(async_session: AsyncSession, redis_client: Redis, data: dict[str, str]) -> UserWithTokens:
    return await user_service.register_user(
        db_session=async_session,
        redis_client=redis_client,
        username=data["username"],
        password=data["password"],
        email=data["email"],
    )


async def test_registration_commits_once_and_creates_user_with_profile(
    async_session: AsyncSession, _shared_fake_redis: Redis
) -> None:
    data = create_fake_user()
    commits = counting_commit(async_session)
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
        async with fail_sql(async_session, _inserts_profile, "injected profile write failure"):
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
        async with fail_sql(async_session, _updates_user, "injected token write failure"):
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
    async_session: AsyncSession,
) -> None:
    """The lazy profile path used by GET /users/me/profile commits in the service, once."""
    user = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()), commit=False)
    user_id = user.id
    await async_session.commit()
    assert await profile_crud.get_by_user_id(async_session, user_id) is None

    commits = counting_commit(async_session)
    first = await user_service.get_or_create_profile(async_session, user_id)
    second = await user_service.get_or_create_profile(async_session, user_id)

    assert second.id == first.id
    assert len(commits) == 1


async def test_update_profile_owns_one_commit_and_survives_a_failed_write(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    profile = await user_service.get_or_create_profile(async_session, user.id)

    commits = counting_commit(async_session)
    updated = await user_service.update_profile(async_session, user.id, ProfileUpdate(bio="Changed bio"))
    assert len(commits) == 1
    assert updated.bio == "Changed bio"
    await async_session.refresh(profile)
    assert profile.bio == "Changed bio"

    async with fail_sql(async_session, _updates_profile, "injected profile update failure"):
        with pytest.raises(RuntimeError, match="injected profile update failure"):
            await user_service.update_profile(async_session, user.id, ProfileUpdate(bio="Never persisted"))
    await async_session.rollback()
    await async_session.refresh(profile)
    assert profile.bio == "Changed bio"
