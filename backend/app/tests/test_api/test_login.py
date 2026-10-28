import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.tests.factory.users import create_fake_user

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.smoke
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

    before = await async_client.get("users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert before.status_code == 200
    assert before.json()["email"] == settings.FIRST_SUPERUSER_EMAIL

    # Step 2: Use the refresh token to obtain a new access token
    refresh_response = await async_client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 200, "Refresh token request failed"

    refreshed_tokens = refresh_response.json()
    new_access_token = refreshed_tokens.get("access_token")
    new_token_type = refreshed_tokens.get("token_type")

    assert new_access_token, "New access token is missing"
    assert new_token_type == "bearer", f"Unexpected new token type: {new_token_type}"

    after = await async_client.get("users/me", headers={"Authorization": f"Bearer {new_access_token}"})
    assert after.status_code == 200
    assert after.json()["id"] == before.json()["id"]

    logout = await async_client.post("auth/logout", headers={"Authorization": f"Bearer {new_access_token}"})
    assert logout.status_code == 200
    rejected = await async_client.post("auth/refresh", json={"refresh_token": refreshed_tokens["refresh_token"]})
    assert rejected.status_code == 400


@pytest.mark.asyncio
async def test_passwordless_account_login_returns_400(async_client: AsyncClient, async_session: AsyncSession) -> None:
    data = create_fake_user()
    async_session.add(User(username=data["username"], email=data["email"], hashed_password=None))
    await async_session.commit()

    response = await async_client.post(
        "/auth/login",
        data={"username": data["email"], "password": data["password"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"
