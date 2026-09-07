import pytest
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.security import verify_password
from app.schemas.user import UserCreate, UserUpdate
from app.tests.factory.users import create_fake_user
from app.tests.utils.utils import random_lower_string


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
