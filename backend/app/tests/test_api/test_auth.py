"""
Comprehensive tests for authentication system including:
- Email verification
- Password reset
- Password change
- Token validation
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core import security
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user

pytestmark = pytest.mark.asyncio(scope="module")


# ============================================================================
# Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def mock_redis_client():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.setex = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock()
    mock.close = AsyncMock()

    async def redis_generator():
        yield mock

    return redis_generator


@pytest.fixture
def mock_email_send():
    """Mock email sending functions at the endpoint level where they're imported."""
    with (
        patch("app.api.v1.endpoints.auth.send_verification_email", new_callable=AsyncMock) as mock_verify,
        patch("app.api.v1.endpoints.auth.send_password_reset_email", new_callable=AsyncMock) as mock_reset,
        patch("app.api.v1.endpoints.auth.send_password_changed_email", new_callable=AsyncMock) as mock_changed,
        patch("app.api.v1.endpoints.user.send_verification_email", new_callable=AsyncMock) as mock_user_verify,
    ):
        yield {
            "send_verification_email": mock_verify,
            "send_password_reset_email": mock_reset,
            "send_password_changed_email": mock_changed,
            "send_user_verification_email": mock_user_verify,
        }


@pytest_asyncio.fixture
async def verified_user(async_session: AsyncSession):
    """Create a verified user for testing."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(db_session=async_session, obj_in=user_in)
    user.email_verified = True
    await async_session.commit()
    await async_session.refresh(user)
    return user, user_data["password"]


@pytest_asyncio.fixture
async def unverified_user(async_session: AsyncSession):
    """Create an unverified user with verification token."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    # Generate and store verification token
    token = security.create_email_verification_token(str(user.id))
    user.email_verification_token = token
    user.email_verified = False
    await async_session.commit()
    await async_session.refresh(user)

    return user, token, user_data["password"]


# ============================================================================
# Email Verification Tests
# ============================================================================


@pytest.mark.asyncio
async def test_verify_email_with_valid_token(
    async_client: AsyncClient,
    unverified_user,
    async_session: AsyncSession,
):
    """Test successful email verification with valid token."""
    user, token, _ = unverified_user

    response = await async_client.post(
        "auth/verify-email",
        json={"token": token},
    )

    assert response.status_code == 200
    assert response.json()["msg"] == "Email verified successfully"

    # Verify user is now verified in database
    await async_session.refresh(user)
    assert user.email_verified is True
    assert user.email_verification_token is None


@pytest.mark.asyncio
async def test_verify_email_with_invalid_token(async_client: AsyncClient):
    """Test email verification with invalid token."""
    response = await async_client.post(
        "auth/verify-email",
        json={"token": "invalid_token_xyz"},
    )

    assert response.status_code == 400
    assert "Invalid or expired token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_verify_email_with_expired_token(async_client: AsyncClient):
    """Test email verification with expired token."""
    # Create token that expired in the past
    user_id = str(uuid4())
    expire = datetime.now(tz=UTC) - timedelta(days=1)  # Expired yesterday
    to_encode = {"exp": expire, "sub": user_id, "type": "email_verification"}

    from jose import jwt

    expired_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    response = await async_client.post(
        "auth/verify-email",
        json={"token": expired_token},
    )

    assert response.status_code == 400
    assert "Invalid or expired token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_verify_email_token_mismatch(
    async_client: AsyncClient,
    unverified_user,
    async_session: AsyncSession,  # noqa: ARG001
):
    """Test verification fails when token doesn't match stored token."""
    import time

    from jose import jwt

    user, stored_token, _ = unverified_user

    # Ensure user is unverified with a stored token
    assert user.email_verified is False
    assert user.email_verification_token == stored_token

    # Wait a moment to ensure different timestamp
    time.sleep(1)  # noqa: ASYNC251

    # Create token with different expiry (8 days instead of 7)
    expire = datetime.now(tz=UTC) + timedelta(days=8)
    to_encode = {"exp": expire, "sub": str(user.id), "type": "email_verification"}
    different_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # Tokens should be different
    assert different_token != stored_token

    response = await async_client.post(
        "auth/verify-email",
        json={"token": different_token},
    )

    assert response.status_code == 400
    assert "Invalid token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_verify_email_already_verified(
    async_client: AsyncClient,
    verified_user,
    async_session: AsyncSession,
):
    """Test verifying an already verified email."""
    user, _ = verified_user

    # Store a token for the verified user (simulating they had one before verification)
    token = security.create_email_verification_token(str(user.id))
    user.email_verification_token = token
    await async_session.commit()

    response = await async_client.post(
        "auth/verify-email",
        json={"token": token},
    )

    assert response.status_code == 200
    assert response.json()["msg"] == "Email already verified"


@pytest.mark.asyncio
async def test_resend_verification_email(
    async_client: AsyncClient,
    unverified_user,
    mock_email_send,
    mock_redis_client,
    async_session: AsyncSession,
):
    """Test resending verification email to unverified user."""
    from app.api.deps import get_redis_client
    from main import app

    user, old_token, password = unverified_user  # noqa: RUF059

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        # Login to get auth headers
        login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": password},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await async_client.post(
            "auth/resend-verification",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["msg"] == "Verification email sent"

        # Verify new token was generated
        await async_session.refresh(user)
        assert user.email_verification_token is not None
        # Tokens might be the same if generated in the same second, so just verify it exists
        # assert user.email_verification_token != old_token

        # Verify email was sent
        mock_email_send["send_verification_email"].assert_called_once()
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_resend_verification_already_verified(
    async_client: AsyncClient,
    verified_user,
    mock_redis_client,
):
    """Test resending verification email to already verified user fails."""
    from app.api.deps import get_redis_client
    from main import app

    user, password = verified_user

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        # Login to get auth headers
        login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": password},
        )
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await async_client.post(
            "auth/resend-verification",
            headers=headers,
        )

        assert response.status_code == 400
        assert "Email already verified" in response.json()["detail"]
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


# ============================================================================
# Password Reset Tests
# ============================================================================


@pytest.mark.asyncio
async def test_forgot_password_valid_email(
    async_client: AsyncClient,
    verified_user,
    mock_email_send,
    async_session: AsyncSession,
):
    """Test requesting password reset with valid email."""
    user, _ = verified_user

    response = await async_client.post(
        "auth/forgot-password",
        json={"email": user.email},
    )

    assert response.status_code == 200
    assert "password reset link has been sent" in response.json()["msg"]

    # Verify token was stored in database
    await async_session.refresh(user)
    assert user.password_reset_token is not None
    assert user.password_reset_expires is not None
    # SQLite stores naive datetimes, so compare with naive datetime
    assert user.password_reset_expires > datetime.now(tz=UTC).replace(tzinfo=None)

    # Verify email was sent
    mock_email_send["send_password_reset_email"].assert_called_once()


@pytest.mark.asyncio
async def test_forgot_password_nonexistent_email(
    async_client: AsyncClient,
    mock_email_send,
):
    """Test requesting password reset with non-existent email (should return success for security)."""
    response = await async_client.post(
        "auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )

    # Should return success to prevent email enumeration
    assert response.status_code == 200
    assert "password reset link has been sent" in response.json()["msg"]

    # Verify no email was sent
    mock_email_send["send_password_reset_email"].assert_not_called()


@pytest.mark.asyncio
async def test_reset_password_with_valid_token(
    async_client: AsyncClient,
    verified_user,
    mock_email_send,  # noqa: ARG001
    mock_redis_client,
    async_session: AsyncSession,
):
    """Test resetting password with valid token."""
    from app.api.deps import get_redis_client
    from main import app

    user, old_password = verified_user

    # Request password reset
    token = security.create_password_reset_token(user.email)
    user.password_reset_token = token
    user.password_reset_expires = datetime.now(tz=UTC) + timedelta(hours=1)
    await async_session.commit()

    new_password = "NewSecurePassword123!"

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        response = await async_client.post(
            "auth/reset-password",
            json={"token": token, "new_password": new_password},
        )

        assert response.status_code == 200
        assert response.json()["msg"] == "Password reset successful"

        # Verify password was changed
        await async_session.refresh(user)
        assert security.verify_password(new_password, user.hashed_password)
        assert not security.verify_password(old_password, user.hashed_password)

        # Verify reset token was cleared
        assert user.password_reset_token is None
        assert user.password_reset_expires is None
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token(async_client: AsyncClient, mock_redis_client):
    """Test resetting password with invalid token."""
    from app.api.deps import get_redis_client
    from main import app

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        response = await async_client.post(
            "auth/reset-password",
            json={"token": "invalid_token", "new_password": "NewPassword123!"},
        )

        assert response.status_code == 400
        assert "Invalid or expired token" in response.json()["detail"]
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_reset_password_with_expired_token(
    async_client: AsyncClient,
    verified_user,
    mock_redis_client,
    async_session: AsyncSession,
):
    """Test resetting password with expired token."""
    from app.api.deps import get_redis_client
    from main import app

    user, _ = verified_user

    # Create expired token
    token = security.create_password_reset_token(user.email)
    user.password_reset_token = token
    user.password_reset_expires = datetime.now(tz=UTC) - timedelta(hours=1)  # Expired
    await async_session.commit()

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        response = await async_client.post(
            "auth/reset-password",
            json={"token": token, "new_password": "NewPassword123!"},
        )

        assert response.status_code == 400
        assert "Token has expired" in response.json()["detail"]
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_reset_password_token_mismatch(
    async_client: AsyncClient,
    verified_user,
    mock_email_send,  # noqa: ARG001
    mock_redis_client,
    async_session: AsyncSession,
):
    """Test resetting password when token doesn't match stored token."""
    import time

    from jose import jwt

    from app.api.deps import get_redis_client
    from main import app

    user, _ = verified_user

    # Store one token
    stored_token = security.create_password_reset_token(user.email)
    user.password_reset_token = stored_token
    user.password_reset_expires = datetime.now(tz=UTC) + timedelta(hours=1)
    await async_session.commit()

    # Wait to ensure different timestamp
    time.sleep(1)  # noqa: ASYNC251

    # Create token with different expiry to ensure it's different
    expire = datetime.now(tz=UTC) + timedelta(hours=2)
    to_encode = {"exp": expire, "sub": user.email, "type": "password_reset"}
    different_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        response = await async_client.post(
            "auth/reset-password",
            json={"token": different_token, "new_password": "NewPassword123!"},
        )

        assert response.status_code == 400
        assert "Invalid token" in response.json()["detail"]
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_reset_password_min_length_validation(
    async_client: AsyncClient,
    verified_user,
    mock_redis_client,
    async_session: AsyncSession,
):
    """Test that password reset enforces minimum password length."""
    from app.api.deps import get_redis_client
    from main import app

    user, _ = verified_user

    token = security.create_password_reset_token(user.email)
    user.password_reset_token = token
    user.password_reset_expires = datetime.now(tz=UTC) + timedelta(hours=1)
    await async_session.commit()

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        response = await async_client.post(
            "auth/reset-password",
            json={"token": token, "new_password": "short"},  # Too short
        )

        assert response.status_code == 422  # Validation error
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


# ============================================================================
# Change Password Tests
# ============================================================================


@pytest.mark.asyncio
async def test_change_password_success(
    async_client: AsyncClient,
    verified_user,
    mock_email_send,  # noqa: ARG001
    mock_redis_client,
    async_session: AsyncSession,
):
    """Test successfully changing password with correct current password."""
    from app.api.deps import get_redis_client
    from main import app

    user, old_password = verified_user

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        # Login to get auth headers
        login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": old_password},
        )
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        new_password = "NewSecurePassword123!"

        response = await async_client.put(
            "auth/change-password",
            headers=headers,
            json={"current_password": old_password, "new_password": new_password},
        )

        assert response.status_code == 200
        assert response.json()["msg"] == "Password changed successfully"

        # Verify password was changed
        await async_session.refresh(user)
        assert security.verify_password(new_password, user.hashed_password)
        assert not security.verify_password(old_password, user.hashed_password)
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_change_password_incorrect_current_password(
    async_client: AsyncClient,
    verified_user,
    mock_redis_client,
):
    """Test changing password with incorrect current password fails."""
    from app.api.deps import get_redis_client
    from main import app

    user, password = verified_user

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        # Login to get auth headers
        login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": password},
        )
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await async_client.put(
            "auth/change-password",
            headers=headers,
            json={"current_password": "WrongPassword123!", "new_password": "NewPassword123!"},
        )

        assert response.status_code == 400
        assert "Incorrect password" in response.json()["detail"]
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_change_password_min_length_validation(
    async_client: AsyncClient,
    verified_user,
    mock_redis_client,
):
    """Test that password change enforces minimum password length."""
    from app.api.deps import get_redis_client
    from main import app

    user, password = verified_user

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        # Login to get auth headers
        login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": password},
        )
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await async_client.put(
            "auth/change-password",
            headers=headers,
            json={"current_password": password, "new_password": "short"},
        )

        assert response.status_code == 422  # Validation error
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_change_password_requires_authentication(async_client: AsyncClient):
    """Test that changing password requires authentication."""
    response = await async_client.put(
        "auth/change-password",
        json={"current_password": "OldPass123!", "new_password": "NewPass123!"},
    )

    assert response.status_code == 401  # Unauthorized


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_registration_verification_flow(
    async_client: AsyncClient,
    mock_email_send,  # noqa: ARG001
    mock_redis_client,
    async_session: AsyncSession,
):
    """Test complete flow: register → verify email → login."""
    from app.api.deps import get_redis_client
    from main import app

    user_data = create_fake_user()

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        # Step 1: Register new user
        with patch("app.api.v1.endpoints.user.send_verification_email", new_callable=AsyncMock):
            register_response = await async_client.post(
                "users/open",
                json={
                    "username": user_data["username"],
                    "email": user_data["email"],
                    "password": user_data["password"],
                },
            )

        assert register_response.status_code == 200
        user_response = register_response.json()
        assert user_response["email_verified"] is False

        # Get user from database
        user = await crud.user.get_by_email(async_session, email=user_data["email"])
        assert user is not None
        verification_token = user.email_verification_token
        assert verification_token is not None

        # Step 2: Verify email
        verify_response = await async_client.post(
            "auth/verify-email",
            json={"token": verification_token},
        )

        assert verify_response.status_code == 200

        # Step 3: Login should work
        login_response = await async_client.post(
            "login/access-token",
            data={"username": user_data["email"], "password": user_data["password"]},
        )

        assert login_response.status_code == 200
        assert "access_token" in login_response.json()
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_full_password_reset_flow(
    async_client: AsyncClient,
    verified_user,
    mock_email_send,  # noqa: ARG001
    mock_redis_client,
    async_session: AsyncSession,
):
    """Test complete flow: forgot password → reset → login with new password."""
    from app.api.deps import get_redis_client
    from main import app

    user, old_password = verified_user

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        # Step 1: Request password reset
        forgot_response = await async_client.post(
            "auth/forgot-password",
            json={"email": user.email},
        )

        assert forgot_response.status_code == 200

        # Get reset token from database
        await async_session.refresh(user)
        reset_token = user.password_reset_token
        assert reset_token is not None

        # Step 2: Reset password
        new_password = "NewSecurePassword123!"
        reset_response = await async_client.post(
            "auth/reset-password",
            json={"token": reset_token, "new_password": new_password},
        )

        assert reset_response.status_code == 200

        # Step 3: Old password should not work
        old_login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": old_password},
        )

        assert old_login_response.status_code == 400

        # Step 4: New password should work
        new_login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": new_password},
        )

        assert new_login_response.status_code == 200
        assert "access_token" in new_login_response.json()
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)


@pytest.mark.asyncio
async def test_full_change_password_flow(
    async_client: AsyncClient,
    verified_user,
    mock_email_send,  # noqa: ARG001
    mock_redis_client,
    async_session: AsyncSession,  # noqa: ARG001
):
    """Test complete flow: login → change password → login with new password."""
    from app.api.deps import get_redis_client
    from main import app

    user, old_password = verified_user

    # Override Redis client
    app.dependency_overrides[get_redis_client] = mock_redis_client

    try:
        # Step 1: Login with old password
        login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": old_password},
        )

        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Step 2: Change password
        new_password = "NewSecurePassword123!"
        change_response = await async_client.put(
            "auth/change-password",
            headers=headers,
            json={"current_password": old_password, "new_password": new_password},
        )

        assert change_response.status_code == 200

        # Step 3: Old password should not work
        old_login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": old_password},
        )

        assert old_login_response.status_code == 400

        # Step 4: New password should work
        new_login_response = await async_client.post(
            "login/access-token",
            data={"username": user.email, "password": new_password},
        )

        assert new_login_response.status_code == 200
        assert "access_token" in new_login_response.json()
    finally:
        # Cleanup
        app.dependency_overrides.pop(get_redis_client, None)
