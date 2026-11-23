"""Authentication: email verification, password reset, password change, token validation."""

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app import crud
from app.api.deps import get_redis_client
from app.core import security
from app.core.config import settings
from app.core.stream_manager import sse_manager
from app.models.user import User
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user
from main import app

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.fixture
def mock_redis_client():
    """Override the Redis dependency with a mock whose GETs always miss."""
    mock = AsyncMock()
    mock.get.return_value = None

    async def _generator():
        yield mock

    app.dependency_overrides[get_redis_client] = _generator
    yield mock
    app.dependency_overrides.pop(get_redis_client, None)


@pytest.fixture
def mock_email_send():
    with (
        patch("app.services.auth_service.send_verification_email", new_callable=AsyncMock) as mock_verify,
        patch("app.services.auth_service.send_password_reset_email", new_callable=AsyncMock) as mock_reset,
        patch("app.services.auth_service.send_password_changed_email", new_callable=AsyncMock) as mock_changed,
        patch("app.services.user_service.send_verification_email", new_callable=AsyncMock) as mock_user_verify,
    ):
        yield {
            "send_verification_email": mock_verify,
            "send_password_reset_email": mock_reset,
            "send_password_changed_email": mock_changed,
            "send_user_verification_email": mock_user_verify,
        }


@pytest_asyncio.fixture
async def verified_user(async_session):
    user_data = create_fake_user()
    user = await crud.user.create(db_session=async_session, obj_in=UserCreate(**user_data))
    user.email_verified = True
    await async_session.commit()
    await async_session.refresh(user)
    return user, user_data["password"]


@pytest_asyncio.fixture
async def unverified_user(async_session):
    user_data = create_fake_user()
    user = await crud.user.create(db_session=async_session, obj_in=UserCreate(**user_data))
    token = security.create_email_verification_token(str(user.id))
    user.email_verification_token = token
    user.email_verified = False
    await async_session.commit()
    await async_session.refresh(user)
    return user, token, user_data["password"]


async def _login(client: AsyncClient, email: str, password: str):
    response = await client.post("auth/login", data={"username": email, "password": password})
    return response, {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _passwordless_user(async_session) -> tuple[User, dict[str, str]]:
    data = create_fake_user()
    async_session.add(User(username=data["username"], email=data["email"], hashed_password=None))
    await async_session.commit()
    user = await crud.user.get_by_email(async_session, email=data["email"])
    assert user is not None
    return user, {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


async def test_verify_email_with_invalid_token(async_client: AsyncClient):
    response = await async_client.post("auth/verify-email", json={"token": "invalid_token_xyz"})
    assert response.status_code == 400
    assert "Invalid or expired token" in response.json()["detail"]


async def test_expired_verification_token_rejected(async_client: AsyncClient, async_session):
    user = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))
    expired_token = jwt.encode(
        {"exp": datetime.now(tz=UTC) - timedelta(days=1), "sub": str(user.id), "type": "email_verification"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    response = await async_client.post("auth/verify-email", json={"token": expired_token})
    assert response.status_code == 400


async def test_resend_verification_email(
    async_client: AsyncClient, unverified_user, mock_email_send, mock_redis_client, async_session
):
    user, _, password = unverified_user
    login, headers = await _login(async_client, user.email, password)
    assert login.status_code == 200

    response = await async_client.post("auth/resend-verification", headers=headers)

    assert response.status_code == 200
    assert response.json()["msg"] == "Verification email sent"
    await async_session.refresh(user)
    assert user.email_verification_token is not None
    mock_email_send["send_verification_email"].assert_called_once()


async def test_resend_verification_already_verified(async_client: AsyncClient, verified_user, mock_redis_client):
    user, password = verified_user
    _, headers = await _login(async_client, user.email, password)

    response = await async_client.post("auth/resend-verification", headers=headers)

    assert response.status_code == 400
    assert "Email already verified" in response.json()["detail"]


async def test_reset_password_with_invalid_token(async_client: AsyncClient, mock_redis_client):
    response = await async_client.post(
        "auth/reset-password", json={"token": "invalid_token", "new_password": "NewPassword123!"}
    )
    assert response.status_code == 400
    assert "Invalid or expired token" in response.json()["detail"]


async def test_change_password_incorrect_current_password(async_client: AsyncClient, verified_user, mock_redis_client):
    user, password = verified_user
    _, headers = await _login(async_client, user.email, password)

    response = await async_client.put(
        "auth/change-password",
        headers=headers,
        json={"current_password": "WrongPassword123!", "new_password": "NewPassword123!"},
    )

    assert response.status_code == 400
    assert "Incorrect password" in response.json()["detail"]


@pytest.mark.smoke
async def test_full_registration_verification_flow(
    async_client: AsyncClient, mock_email_send, mock_redis_client, async_session
):
    user_data = create_fake_user()

    register_response = await async_client.post(
        "users/open", json={k: user_data[k] for k in ("username", "email", "password")}
    )

    assert register_response.status_code == 200
    assert register_response.json()["email_verified"] is False

    user = await crud.user.get_by_email(async_session, email=user_data["email"])
    assert user is not None
    verification_token = user.email_verification_token
    assert verification_token is not None

    verify_response = await async_client.post("auth/verify-email", json={"token": verification_token})
    assert verify_response.status_code == 200

    login_response = await async_client.post(
        "auth/login", data={"username": user_data["email"], "password": user_data["password"]}
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()


async def test_full_password_reset_flow(
    async_client: AsyncClient, verified_user, mock_email_send, mock_redis_client, async_session
):
    user, old_password = verified_user

    forgot_response = await async_client.post("auth/forgot-password", json={"email": user.email})
    assert forgot_response.status_code == 200

    await async_session.refresh(user)
    reset_token = user.password_reset_token
    assert reset_token is not None

    new_password = "NewSecurePassword123!"
    reset_response = await async_client.post(
        "auth/reset-password", json={"token": reset_token, "new_password": new_password}
    )
    assert reset_response.status_code == 200

    old_login_response = await async_client.post("auth/login", data={"username": user.email, "password": old_password})
    assert old_login_response.status_code == 400

    new_login_response = await async_client.post("auth/login", data={"username": user.email, "password": new_password})
    assert new_login_response.status_code == 200
    assert "access_token" in new_login_response.json()


async def test_full_change_password_flow(
    async_client: AsyncClient, verified_user, mock_email_send, mock_redis_client, async_session
):
    user, old_password = verified_user

    login_response, headers = await _login(async_client, user.email, old_password)
    assert login_response.status_code == 200

    new_password = "NewSecurePassword123!"
    change_response = await async_client.put(
        "auth/change-password",
        headers=headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert change_response.status_code == 200

    old_login_response = await async_client.post("auth/login", data={"username": user.email, "password": old_password})
    assert old_login_response.status_code == 400

    new_login_response = await async_client.post("auth/login", data={"username": user.email, "password": new_password})
    assert new_login_response.status_code == 200
    assert "access_token" in new_login_response.json()


@pytest.mark.parametrize("payload", [{"sub": str(uuid4()), "exp": 1}, {"sub": "not-a-uuid"}, {}])
async def test_invalid_access_credentials_request_reauthentication(async_client: AsyncClient, payload: dict):
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = await async_client.get("users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"] == "Could not validate credentials"


async def test_change_password_on_passwordless_account_returns_actionable_400(
    async_client: AsyncClient, async_session, mock_redis_client
):
    user, headers = await _passwordless_user(async_session)

    response = await async_client.put(
        "auth/change-password",
        headers=headers,
        json={"current_password": "anything", "new_password": "NewPassword123!"},
    )

    assert response.status_code == 400
    assert "No password set for this account" in response.json()["detail"]


async def test_passwordless_account_can_recover_through_password_reset(
    async_client: AsyncClient, async_session, mock_email_send, mock_redis_client
):
    user, headers = await _passwordless_user(async_session)
    before = await async_client.get("users/me", headers=headers)
    assert before.status_code == 200
    assert before.json()["has_password"] is False
    assert "hashed_password" not in before.json()

    forgot = await async_client.post("auth/forgot-password", json={"email": user.email})
    assert forgot.status_code == 200

    await async_session.refresh(user)
    assert user.password_reset_token is not None

    new_password = "RecoveredPassword123!"
    reset = await async_client.post(
        "auth/reset-password", json={"token": user.password_reset_token, "new_password": new_password}
    )
    assert reset.status_code == 200

    login = await async_client.post("auth/login", data={"username": user.email, "password": new_password})
    assert login.status_code == 200
    assert "access_token" in login.json()
    after = await async_client.get("users/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert after.status_code == 200
    assert after.json()["has_password"] is True
    assert after.json()["id"] == str(user.id)
    assert "hashed_password" not in after.json()


@pytest.mark.parametrize("path", ["users/me", "stream/notifications"])
@pytest.mark.parametrize("purpose", ["refresh", "email_verification", "password_reset", None])
async def test_non_access_tokens_cannot_authenticate_http(
    async_client: AsyncClient, verified_user, _shared_fake_redis, purpose: str | None, path: str
):
    user, _ = verified_user
    if purpose == "refresh":
        token = await security.create_refresh_token(user.id, _shared_fake_redis)
        await security.invalidate_refresh_token(str(user.id), _shared_fake_redis)
    elif purpose == "email_verification":
        token = security.create_email_verification_token(user.id)
    elif purpose == "password_reset":
        token = security.create_password_reset_token(user.id)
    else:
        token = jwt.encode(
            {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
    response = await async_client.get(path, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("purpose", ["access", "email_verification", "password_reset", None])
async def test_refresh_rejects_wrong_purpose_even_if_stored(
    async_client: AsyncClient, verified_user, _shared_fake_redis, purpose: str | None
):
    user, _ = verified_user
    payload = {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=5)}
    if purpose is not None:
        payload["type"] = purpose
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    key = f"refresh_token:{user.id}"
    await _shared_fake_redis.setex(key, 300, token)

    response = await async_client.post("auth/refresh", json={"refresh_token": token})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid refresh token"
    assert await _shared_fake_redis.get(key) == token


async def test_access_token_opens_only_its_users_notification_stream(async_client: AsyncClient, verified_user):
    user, _ = verified_user
    user_id = user.id
    token = security.create_access_token(user_id)
    request = asyncio.create_task(
        async_client.get("stream/notifications", headers={"Authorization": f"Bearer {token}"})
    )
    try:
        async with asyncio.timeout(3):
            while not sse_manager._subscribers.get("notifications", {}).get(user_id):
                if request.done():
                    response = await request
                    pytest.fail(f"Stream ended before subscribing: {response.status_code}")
                await asyncio.sleep(0)
            await sse_manager.publish(user_id, "notifications", {"event_id": "auth-probe", "data": {"msg": "hello"}})
            await sse_manager.close()
            response = await request
        assert response.status_code == 200
        assert "event: notification" in response.text
        assert "hello" in response.text
    finally:
        request.cancel()
        with suppress(asyncio.CancelledError):
            await request
        await sse_manager.close()
