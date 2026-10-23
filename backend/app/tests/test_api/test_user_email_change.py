"""Tests for email changes via PUT /users/me.

Changing an account email must re-verify the new address: the old token stops
working, a fresh token is stored and mailed to the new address, duplicates are
rejected (including soft-deleted owners), and a same-address request is a no-op.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core import security
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user
from app.tests.test_api.test_user import create_isolated_user_with_token

pytestmark = pytest.mark.asyncio(scope="module")


def _new_email() -> str:
    return f"{uuid4().hex[:8]}@example.com"


async def _stored_user(async_session: AsyncSession, email: str):
    user = await crud.user.get_by_email(db_session=async_session, email=email)
    assert user is not None
    return user


async def test_change_email_resets_verification_and_issues_new_token(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """A changed address becomes unverified and carries a new verification token."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    user.email_verified = True
    user.email_verification_token = "stale-verification-token"
    await async_session.commit()

    new_email = _new_email()
    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock):
        response = await async_client.put(
            "/users/me",
            json={"email": new_email},
            headers=token_headers,
        )

    assert response.status_code == 200
    assert response.json()["email"] == new_email
    assert response.json()["email_verified"] is False

    await async_session.refresh(user)
    assert user.email == new_email
    assert user.email_verified is False
    assert user.email_verification_token is not None
    assert user.email_verification_token != "stale-verification-token"
    assert user.email_changed_at is not None


async def test_change_email_sends_verification_to_new_address(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """The verification mail goes to the new address and carries the stored token."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    new_email = _new_email()
    mock_send = AsyncMock()

    with patch("app.services.user_service.send_verification_email", mock_send):
        response = await async_client.put(
            "/users/me",
            json={"email": new_email},
            headers=token_headers,
        )

    assert response.status_code == 200
    mock_send.assert_awaited_once()
    sent = mock_send.await_args.kwargs
    assert sent["email_to"] == new_email
    assert sent["username"] == user.username

    await async_session.refresh(user)
    assert sent["token"] == user.email_verification_token


async def test_change_email_to_existing_email_conflicts(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """An address owned by another row is a 409, including when that owner is soft-deleted."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)

    active_data = create_fake_user()
    await crud.user.create(db_session=async_session, obj_in=UserCreate(**active_data))

    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock):
        active_response = await async_client.put(
            "/users/me",
            json={"email": active_data["email"]},
            headers=token_headers,
        )
    assert active_response.status_code == 409

    deleted_data = create_fake_user()
    deleted = await crud.user.create(db_session=async_session, obj_in=UserCreate(**deleted_data))
    deleted.soft_delete()
    async_session.add(deleted)
    await async_session.commit()
    assert (
        await crud.user.get_by_email(db_session=async_session, email=deleted_data["email"], include_deleted=True)
        is not None
    )

    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock):
        deleted_response = await async_client.put(
            "/users/me",
            json={"email": deleted_data["email"]},
            headers=token_headers,
        )
    assert deleted_response.status_code == 409


async def test_change_email_old_token_cannot_verify_new_address(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """The pre-change token is rejected even when both mints land in the same second."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    old_token = security.create_email_verification_token(str(user.id))
    user.email_verification_token = old_token
    await async_session.commit()

    new_email = _new_email()
    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock):
        change_response = await async_client.put(
            "/users/me",
            json={"email": new_email},
            headers=token_headers,
        )
    assert change_response.status_code == 200

    old_token_response = await async_client.post("auth/verify-email", json={"token": old_token})
    assert old_token_response.status_code == 400

    await async_session.refresh(user)
    new_token = user.email_verification_token
    assert new_token is not None
    assert new_token != old_token
    new_token_response = await async_client.post("auth/verify-email", json={"token": new_token})
    assert new_token_response.status_code == 200


async def test_change_email_to_same_address_keeps_verification(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Re-submitting the current address is a no-op that keeps verification and sends no mail."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    user.email_verified = True
    await async_session.commit()

    mock_send = AsyncMock()
    with patch("app.services.user_service.send_verification_email", mock_send):
        response = await async_client.put(
            "/users/me",
            json={"email": user_data["email"]},
            headers=token_headers,
        )

    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    mock_send.assert_not_awaited()

    await async_session.refresh(user)
    assert user.email_verified is True


async def test_verified_user_change_email_becomes_unverified(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """The headline behavior: a verified account loses verification when its email changes."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    user.email_verified = True
    await async_session.commit()
    assert user.email_verified is True

    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock):
        response = await async_client.put(
            "/users/me",
            json={"email": _new_email()},
            headers=token_headers,
        )

    assert response.status_code == 200
    assert response.json()["email_verified"] is False
    await async_session.refresh(user)
    assert user.email_verified is False


async def test_change_email_send_failure_returns_502_and_resend_recovers(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """A failed delivery surfaces as 502 while the stored state stays recoverable via resend."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    mock_send = AsyncMock(side_effect=[RuntimeError("smtp down"), None])

    with (
        patch("app.services.user_service.send_verification_email", mock_send),
        patch("app.services.auth_service.send_verification_email", mock_send),
    ):
        change_response = await async_client.put(
            "/users/me",
            json={"email": _new_email()},
            headers=token_headers,
        )
        assert change_response.status_code == 502

        resend_response = await async_client.post(
            "auth/resend-verification",
            headers=token_headers,
        )

    assert resend_response.status_code == 200
    mock_send.assert_awaited()
    assert mock_send.await_count == 2
    await async_session.refresh(user)
    assert user.email_verified is False


async def test_email_change_is_rate_limited(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock):
        first = await async_client.put(
            "/users/me",
            json={"email": _new_email()},
            headers=token_headers,
        )
        assert first.status_code == 200

        second = await async_client.put(
            "/users/me",
            json={"email": _new_email()},
            headers=token_headers,
        )

    assert second.status_code == 429
    assert "can be changed again" in second.json()["detail"]


async def test_email_change_allowed_after_cooldown(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    user.email_changed_at = datetime.utcnow() - timedelta(days=settings.EMAIL_CHANGE_COOLDOWN_DAYS + 1)
    await async_session.commit()

    with patch("app.services.user_service.send_verification_email", new_callable=AsyncMock):
        response = await async_client.put(
            "/users/me",
            json={"email": _new_email()},
            headers=token_headers,
        )

    assert response.status_code == 200


async def test_update_me_saves_username_email_and_password_together_on_mail_failure(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """A mail failure after the single commit must not skip the password or partial fields."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    new_username = f"nyx_{uuid4().hex[:8]}"
    new_email = _new_email()
    new_password = f"pw-{uuid4().hex[:12]}"

    with patch(
        "app.services.user_service.send_verification_email",
        new=AsyncMock(side_effect=RuntimeError("smtp down")),
    ):
        response = await async_client.put(
            "/users/me",
            json={"username": new_username, "email": new_email, "password": new_password},
            headers=token_headers,
        )

    assert response.status_code == 502

    await async_session.refresh(user)
    assert user.username == new_username
    assert user.email == new_email
    assert user.email_verified is False
    assert security.verify_password(new_password, user.hashed_password)
    assert not security.verify_password(user_data["password"], user.hashed_password)


async def test_email_conflict_from_lost_race_returns_409(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """A competing writer that wins after the pre-check is mapped to 409, not a server error."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)
    other = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))

    with (
        patch("app.services.user_service.UserService._assert_email_available", new=AsyncMock()),
        patch("app.services.user_service.send_verification_email", new_callable=AsyncMock),
    ):
        response = await async_client.put(
            "/users/me",
            json={"email": other.email},
            headers=token_headers,
        )

    assert response.status_code == 409
    assert "already in use" in response.json()["detail"]
