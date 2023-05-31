import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_get_access_token(async_client: AsyncClient) -> None:
    login_data = {
        "username": settings.FIRST_SUPERUSER_EMAIL,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    response = await async_client.post("/login/access-token", data=login_data)
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
    response = await async_client.post("/login/access-token", data=login_data)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_use_access_token(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = await async_client.post(
        "/login/test-token",
        headers=superuser_token_headers,
    )
    result = response.json()
    assert response.status_code == 200
    assert "email" in result
