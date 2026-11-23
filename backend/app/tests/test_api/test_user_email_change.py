"""Email changes via PUT /users/me must re-verify the new address, reject duplicates
(including soft-deleted owners), and treat a same-address request as a no-op."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core import security
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user
from app.tests.test_api.test_user import create_isolated_user_with_token
from app.utils.time import utcnow

pytestmark = pytest.mark.asyncio(scope="module")

SEND = "app.services.user_service.send_verification_email"


def _new_email() -> str:
    return f"{uuid4().hex[:8]}@example.com"


async def _stored_user(async_session: AsyncSession, email: str):
    user = await crud.user.get_by_email(db_session=async_session, email=email)
    assert user is not None
    return user


async def _change_email(client, headers, email, mock=None):
    mock = mock if mock is not None else AsyncMock()
    with patch(SEND, mock):
        response = await client.put("/users/me", json={"email": email}, headers=headers)
    return response, mock


async def test_change_email_resets_verification_and_issues_new_token(async_client, async_session):
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    user.email_verified = True
    user.email_verification_token = "stale-verification-token"
    await async_session.commit()
    new_email = _new_email()
    response, _ = await _change_email(async_client, headers, new_email)
    assert response.status_code == 200
    assert response.json()["email"] == new_email
    assert response.json()["email_verified"] is False
    await async_session.refresh(user)
    assert user.email == new_email
    assert user.email_verified is False
    assert user.email_verification_token is not None
    assert user.email_verification_token != "stale-verification-token"
    assert user.email_changed_at is not None


async def test_change_email_sends_verification_to_new_address(async_client, async_session):
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    new_email = _new_email()
    response, mock_send = await _change_email(async_client, headers, new_email)
    assert response.status_code == 200
    mock_send.assert_awaited_once()
    sent = mock_send.await_args.kwargs
    assert sent["email_to"] == new_email
    assert sent["username"] == user.username
    await async_session.refresh(user)
    assert sent["token"] == user.email_verification_token


async def test_change_email_to_existing_email_conflicts(async_client, async_session):
    headers, _ = await create_isolated_user_with_token(async_client, async_session)
    active_data = create_fake_user()
    await crud.user.create(db_session=async_session, obj_in=UserCreate(**active_data))
    active_response, _ = await _change_email(async_client, headers, active_data["email"])
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
    deleted_response, _ = await _change_email(async_client, headers, deleted_data["email"])
    assert deleted_response.status_code == 409


async def test_change_email_old_token_cannot_verify_new_address(async_client, async_session):
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    old_token = security.create_email_verification_token(str(user.id))
    user.email_verification_token = old_token
    await async_session.commit()
    new_email = _new_email()
    change_response, _ = await _change_email(async_client, headers, new_email)
    assert change_response.status_code == 200
    old_token_response = await async_client.post("auth/verify-email", json={"token": old_token})
    assert old_token_response.status_code == 400
    await async_session.refresh(user)
    new_token = user.email_verification_token
    assert new_token is not None
    assert new_token != old_token
    new_token_response = await async_client.post("auth/verify-email", json={"token": new_token})
    assert new_token_response.status_code == 200


async def test_change_email_to_same_address_keeps_verification(async_client, async_session):
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    user.email_verified = True
    await async_session.commit()
    response, mock_send = await _change_email(async_client, headers, user_data["email"])
    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    mock_send.assert_not_awaited()
    await async_session.refresh(user)
    assert user.email_verified is True


async def test_verified_user_change_email_becomes_unverified(async_client, async_session):
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    user.email_verified = True
    await async_session.commit()
    assert user.email_verified is True
    response, _ = await _change_email(async_client, headers, _new_email())
    assert response.status_code == 200
    assert response.json()["email_verified"] is False
    await async_session.refresh(user)
    assert user.email_verified is False


async def test_change_email_send_failure_returns_502_and_resend_recovers(async_client, async_session):
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    mock_send = AsyncMock(side_effect=[RuntimeError("smtp down"), None])
    with (
        patch(SEND, mock_send),
        patch("app.services.auth_service.send_verification_email", mock_send),
    ):
        change_response = await async_client.put("/users/me", json={"email": _new_email()}, headers=headers)
        assert change_response.status_code == 502
        resend_response = await async_client.post("auth/resend-verification", headers=headers)
    assert resend_response.status_code == 200
    mock_send.assert_awaited()
    assert mock_send.await_count == 2
    await async_session.refresh(user)
    assert user.email_verified is False


async def test_email_change_is_rate_limited(async_client, async_session):
    headers, _ = await create_isolated_user_with_token(async_client, async_session)
    with patch(SEND, new_callable=AsyncMock):
        first = await async_client.put("/users/me", json={"email": _new_email()}, headers=headers)
        assert first.status_code == 200
        second = await async_client.put("/users/me", json={"email": _new_email()}, headers=headers)
    assert second.status_code == 429
    assert "can be changed again" in second.json()["detail"]


async def test_email_change_allowed_after_cooldown(async_client, async_session):
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    user.email_changed_at = utcnow() - timedelta(days=settings.EMAIL_CHANGE_COOLDOWN_DAYS + 1)
    await async_session.commit()
    response, _ = await _change_email(async_client, headers, _new_email())
    assert response.status_code == 200


async def test_update_me_saves_username_email_and_password_together_on_mail_failure(async_client, async_session):
    """A mail failure after the single commit must not skip the password or partial fields."""
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await _stored_user(async_session, user_data["email"])
    new_username = f"nyx_{uuid4().hex[:8]}"
    new_email = _new_email()
    new_password = f"pw-{uuid4().hex[:12]}"
    with patch(SEND, new=AsyncMock(side_effect=RuntimeError("smtp down"))):
        response = await async_client.put(
            "/users/me",
            json={"username": new_username, "email": new_email, "password": new_password},
            headers=headers,
        )
    assert response.status_code == 502
    await async_session.refresh(user)
    assert user.username == new_username
    assert user.email == new_email
    assert user.email_verified is False
    assert security.verify_password(new_password, user.hashed_password)
    assert not security.verify_password(user_data["password"], user.hashed_password)


async def test_email_conflict_from_lost_race_returns_409(async_client, async_session):
    headers, _ = await create_isolated_user_with_token(async_client, async_session)
    other = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))
    with (
        patch("app.services.user_service.UserService._assert_email_available", new=AsyncMock()),
        patch(SEND, new_callable=AsyncMock),
    ):
        response = await async_client.put("/users/me", json={"email": other.email}, headers=headers)
    assert response.status_code == 409
    assert "already in use" in response.json()["detail"]
