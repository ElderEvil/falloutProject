import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_get_users_superuser_me(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = await async_client.get("/users/me", headers=superuser_token_headers)
    current_user = response.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"]
    assert current_user["email"] == settings.FIRST_SUPERUSER_EMAIL


@pytest.mark.asyncio
async def test_get_users_normal_user_me(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = await async_client.get("/users/me", headers=normal_user_token_headers)
    current_user = response.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"] is False
    assert current_user["email"] == settings.EMAIL_TEST_USER


@pytest.mark.asyncio
async def test_create_user_new_email(
    async_client: AsyncClient,
    superuser_token_headers: dict,
    async_session: AsyncSession,
) -> None:
    user_data = create_fake_user()
    response = await async_client.post(
        "/users/",
        headers=superuser_token_headers,
        json=user_data,
    )
    assert 200 <= response.status_code < 300
    created_user = response.json()
    user = await crud.user.get_by_email(db_session=async_session, email=user_data["email"])
    assert user
    assert user.email == created_user["email"]


@pytest.mark.asyncio
async def test_get_existing_user(
    async_client: AsyncClient,
    superuser_token_headers: dict,
    async_session: AsyncSession,
) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(db_session=async_session, obj_in=user_in)
    user_id = user.id
    response = await async_client.get(
        f"/users/{user_id}",
        headers=superuser_token_headers,
    )
    assert 200 <= response.status_code < 300
    api_user = response.json()
    existing_user = await crud.user.get_by_email(db_session=async_session, email=user_data["email"])
    assert existing_user
    assert existing_user.email == api_user["email"]


@pytest.mark.asyncio
async def test_create_user_existing_username(
    async_client: AsyncClient,
    superuser_token_headers: dict,
    async_session: AsyncSession,
) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    await crud.user.create(db_session=async_session, obj_in=user_in)
    response = await async_client.post(
        "/users/",
        headers=superuser_token_headers,
        json=user_data,
    )
    created_user = response.json()
    assert response.status_code == 409
    assert "_id" not in created_user


@pytest.mark.asyncio
async def test_create_user_by_normal_user(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    user_data = create_fake_user()
    response = await async_client.post(
        "/users/",
        headers=normal_user_token_headers,
        json=user_data,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_retrieve_users(
    async_client: AsyncClient,
    superuser_token_headers: dict,
    async_session: AsyncSession,
) -> None:
    user_1_data = create_fake_user()
    user_1_in = UserCreate(**user_1_data)
    await crud.user.create(db_session=async_session, obj_in=user_1_in)

    user_2_data = create_fake_user()
    user_2_in = UserCreate(**user_2_data)
    await crud.user.create(db_session=async_session, obj_in=user_2_in)

    response = await async_client.get("/users/", headers=superuser_token_headers)
    all_users = response.json()

    assert len(all_users) > 1
    for item in all_users:
        assert "email" in item
