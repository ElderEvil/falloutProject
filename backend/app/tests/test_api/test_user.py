import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user
from app.tests.utils.user import user_authentication_headers

pytestmark = pytest.mark.asyncio(scope="module")


async def create_isolated_user_with_token(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> tuple[dict[str, str], dict]:
    """
    Create an isolated user and return auth token headers along with user data.

    This ensures tests don't share state with other tests using shared fixtures.

    :param async_client: Test HTTP client
    :param async_session: Database session
    :returns: Tuple of (token_headers, user_data_dict)
    """
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    token_headers = await user_authentication_headers(
        client=async_client,
        email=user_data["email"],
        password=user_data["password"],
    )

    return token_headers, {"id": str(user.id), **user_data}


@pytest.mark.smoke
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


@pytest.mark.smoke
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


# =============================================================================
# Profile Tests (migrated from test_profile.py)
# =============================================================================


@pytest.mark.asyncio
async def test_update_profile_partial(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Test partially updating profile (only bio) with isolated user."""
    # Create isolated user to avoid shared state issues
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    # First, get the profile to ensure it exists
    await async_client.get("/users/me/profile", headers=token_headers)

    update_data = {"bio": "Updated bio only"}
    response = await async_client.put("/users/me/profile", json=update_data, headers=token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["bio"] == update_data["bio"]
