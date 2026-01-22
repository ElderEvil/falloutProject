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


# =============================================================================
# Profile Tests (migrated from test_profile.py)
# =============================================================================


@pytest.mark.asyncio
async def test_get_my_profile(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Test getting current user's profile."""
    response = await async_client.get("/users/me/profile", headers=normal_user_token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert "id" in profile
    assert "user_id" in profile
    assert "bio" in profile
    assert "avatar_url" in profile
    assert "preferences" in profile
    assert "total_dwellers_created" in profile
    assert "total_caps_earned" in profile
    assert "total_explorations" in profile
    assert "total_rooms_built" in profile
    assert "created_at" in profile
    assert "updated_at" in profile


@pytest.mark.asyncio
async def test_update_my_profile(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Test updating current user's profile."""
    update_data = {
        "bio": "I am a vault dweller and I love Fallout!",
        "avatar_url": "https://example.com/avatar.png",
        "preferences": {"theme": "dark", "notifications": True},
    }
    response = await async_client.put("/users/me/profile", json=update_data, headers=normal_user_token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["bio"] == update_data["bio"]
    assert profile["avatar_url"] == update_data["avatar_url"]
    assert profile["preferences"] == update_data["preferences"]


@pytest.mark.asyncio
async def test_update_profile_partial(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Test partially updating profile (only bio)."""
    update_data = {"bio": "Updated bio only"}
    response = await async_client.put("/users/me/profile", json=update_data, headers=normal_user_token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["bio"] == update_data["bio"]


@pytest.mark.asyncio
async def test_get_superuser_profile(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test that superuser also has a profile auto-created."""
    response = await async_client.get("/users/me/profile", headers=superuser_token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["user_id"] is not None
    assert profile["total_dwellers_created"] == 0
    assert profile["total_caps_earned"] == 0
    assert profile["total_explorations"] == 0
    assert profile["total_rooms_built"] == 0


@pytest.mark.asyncio
async def test_profile_statistics_not_directly_editable(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Test that statistics cannot be directly updated via the API."""
    # Try to update statistics (should be ignored)
    update_data = {
        "bio": "New bio",
        "total_dwellers_created": 9999,  # This should be ignored
        "total_caps_earned": 9999,  # This should be ignored
    }
    response = await async_client.put("/users/me/profile", json=update_data, headers=normal_user_token_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile["bio"] == "New bio"
    # Statistics should remain at 0 (not updated to 9999)
    assert profile["total_dwellers_created"] == 0
    assert profile["total_caps_earned"] == 0
