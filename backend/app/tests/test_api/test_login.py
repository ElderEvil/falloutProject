import pytest
from httpx import AsyncClient

from app.core.config import settings

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_get_access_token(async_client: AsyncClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER_EMAIL,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    response = await async_client.post("/auth/login", data=login_data)
    tokens = response.json()
    assert response.status_code == 200
    assert "access_token" in tokens
    assert tokens["access_token"]


@pytest.mark.asyncio
async def test_get_access_token_incorrect_credentials(async_client: AsyncClient) -> None:
    login_data = {
        "username": "invalid_user",
        "password": "invalid_password",
    }
    response = await async_client.post("/auth/login", data=login_data)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_refresh_token(async_client: AsyncClient) -> None:
    # Step 1: Obtain access and refresh tokens through login
    login_data = {
        "username": settings.FIRST_SUPERUSER_EMAIL,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    response = await async_client.post("/auth/login", data=login_data)
    assert response.status_code == 200, "Login failed"

    tokens = response.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    token_type = tokens.get("token_type")

    assert access_token, "Access token is missing"
    assert refresh_token, "Refresh token is missing"
    assert token_type == "bearer", f"Unexpected token type: {token_type}"

    # Step 2: Use the refresh token to obtain a new access token
    refresh_response = await async_client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 200, "Refresh token request failed"

    refreshed_tokens = refresh_response.json()
    new_access_token = refreshed_tokens.get("access_token")
    new_token_type = refreshed_tokens.get("token_type")

    assert new_access_token, "New access token is missing"
    assert new_token_type == "bearer", f"Unexpected new token type: {new_token_type}"
