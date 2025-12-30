import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(scope="module")


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
