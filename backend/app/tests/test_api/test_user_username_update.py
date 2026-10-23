"""Tests for username updates via PUT /users/me.

Username editing must respect the model's uniqueness constraint and length
bounds while remaining optional (no-op when the field is absent).
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user
from app.tests.test_api.test_user import create_isolated_user_with_token

pytestmark = pytest.mark.asyncio(scope="module")


async def test_update_own_username(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """A user can change their own username and the change persists."""
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)

    new_username = f"nyx_{uuid4().hex[:8]}"
    response = await async_client.put(
        "/users/me",
        json={"username": new_username},
        headers=token_headers,
    )
    assert response.status_code == 200
    assert response.json()["username"] == new_username

    stored = await crud.user.get_by_username(db_session=async_session, username=new_username)
    assert stored is not None
    assert stored.email == user_data["email"]


async def test_update_username_to_taken_name_conflicts(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Changing to a username another active user holds maps to 409, not a 500."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)
    other_data = create_fake_user()
    await crud.user.create(db_session=async_session, obj_in=UserCreate(**other_data))

    response = await async_client.put(
        "/users/me",
        json={"username": other_data["username"]},
        headers=token_headers,
    )
    assert response.status_code == 409


async def test_update_username_rejects_short_value(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """The 3-character minimum from the model applies to username edits."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    response = await async_client.put(
        "/users/me",
        json={"username": "ab"},
        headers=token_headers,
    )
    assert response.status_code == 400
    assert "3 and 32" in response.json()["detail"]


async def test_update_username_rejects_overlong_value(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """The 32-character maximum from the model applies to username edits."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    response = await async_client.put(
        "/users/me",
        json={"username": "x" * 33},
        headers=token_headers,
    )
    assert response.status_code == 400
    assert "3 and 32" in response.json()["detail"]


async def test_username_change_is_rate_limited(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)

    first = await async_client.put(
        "/users/me",
        json={"username": f"nyx_{uuid4().hex[:8]}"},
        headers=token_headers,
    )
    assert first.status_code == 200

    second = await async_client.put(
        "/users/me",
        json={"username": f"nyx_{uuid4().hex[:8]}"},
        headers=token_headers,
    )
    assert second.status_code == 429
    assert "can be changed again" in second.json()["detail"]


async def test_username_change_allowed_after_cooldown(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    token_headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await crud.user.get_by_email(db_session=async_session, email=user_data["email"])
    assert user is not None
    user.username_changed_at = datetime.utcnow() - timedelta(days=settings.USERNAME_CHANGE_COOLDOWN_DAYS + 1)
    await async_session.commit()

    response = await async_client.put(
        "/users/me",
        json={"username": f"nyx_{uuid4().hex[:8]}"},
        headers=token_headers,
    )
    assert response.status_code == 200


async def test_resubmitting_the_same_username_is_not_rate_limited(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)
    username = f"nyx_{uuid4().hex[:8]}"

    first = await async_client.put("/users/me", json={"username": username}, headers=token_headers)
    assert first.status_code == 200

    second = await async_client.put("/users/me", json={"username": username}, headers=token_headers)
    assert second.status_code == 200


async def test_username_conflict_from_lost_race_returns_409(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """A competing writer that wins after the pre-check is mapped to 409, not a server error."""
    token_headers, _ = await create_isolated_user_with_token(async_client, async_session)
    other = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))

    with patch("app.services.user_service.crud.user.get_by_username", new=AsyncMock(return_value=None)):
        response = await async_client.put(
            "/users/me",
            json={"username": other.username},
            headers=token_headers,
        )

    assert response.status_code == 409
    assert "already taken" in response.json()["detail"]
