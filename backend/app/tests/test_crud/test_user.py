import pytest
from fastapi.encoders import jsonable_encoder
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.security import verify_password
from app.crud.user import build_user_model
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user import UserCreate, UserUpdate
from app.tests.factory.users import create_fake_user
from app.tests.utils.utils import random_lower_string
from app.utils.exceptions import ResourceConflictException


@pytest.mark.asyncio
async def test_authenticate_user(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    authenticated_user = await crud.user.authenticate(
        async_session,
        email=user_data["email"],
        password=user_data["password"],
    )
    assert authenticated_user
    assert user.email == authenticated_user.email


@pytest.mark.asyncio
async def test_not_authenticate_user(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user = await crud.user.authenticate(async_session, email=user_data["email"], password=user_data["password"])
    assert user is None


@pytest.mark.asyncio
async def test_passwordless_user_cannot_authenticate(async_session: AsyncSession) -> None:
    data = create_fake_user()
    async_session.add(User(username=data["username"], email=data["email"], hashed_password=None))
    await async_session.commit()

    assert await crud.user.authenticate(async_session, email=data["email"], password=data["password"]) is None


@pytest.mark.asyncio
async def test_create_commits_user_and_profile_together(async_session: AsyncSession) -> None:
    data = create_fake_user()

    user = await crud.user.create(async_session, obj_in=UserCreate(**data))

    profile = await async_session.execute(select(UserProfile).where(col(UserProfile.user_id) == user.id))
    assert profile.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_create_duplicate_still_raises_conflict(async_session: AsyncSession) -> None:
    data = create_fake_user()
    await crud.user.create(async_session, obj_in=UserCreate(**data))

    with pytest.raises(ResourceConflictException) as exc_info:
        await crud.user.create(async_session, obj_in=UserCreate(**data))

    assert "User already exists" in exc_info.value.detail


@pytest.mark.asyncio
async def test_profile_failure_leaves_no_user_row(async_session: AsyncSession, monkeypatch) -> None:
    class _FailingProfile:
        def __init__(self, **_kwargs):
            raise RuntimeError("profile failed")

    import importlib

    user_crud_module = importlib.import_module("app.crud.user")
    monkeypatch.setattr(user_crud_module, "UserProfile", _FailingProfile)
    data = create_fake_user()

    with pytest.raises(RuntimeError):
        await crud.user.create(async_session, obj_in=UserCreate(**data))
    await async_session.rollback()

    assert await crud.user.get_by_email(async_session, email=data["email"]) is None


def test_build_user_model_supports_passwordless_accounts() -> None:
    with_password = build_user_model(username="alice", email="alice@example.com", password="Secret123!")
    without_password = build_user_model(username="bob", email="bob@example.com")

    assert with_password.hashed_password is not None
    assert without_password.hashed_password is None
