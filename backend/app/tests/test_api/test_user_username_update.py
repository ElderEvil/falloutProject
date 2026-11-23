"""Username updates via PUT /users/me must respect uniqueness and length bounds while
remaining optional (no-op when the field is absent)."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app import crud
from app.core.config import settings
from app.schemas.user import UserCreate
from app.tests.factory.users import create_fake_user
from app.tests.test_api.test_user import create_isolated_user_with_token
from app.utils.time import utcnow

pytestmark = pytest.mark.asyncio(scope="module")


async def _put_username(client, headers, username: str):
    return await client.put("/users/me", json={"username": username}, headers=headers)


async def test_update_own_username(async_client, async_session) -> None:
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    new_username = f"nyx_{uuid4().hex[:8]}"
    response = await _put_username(async_client, headers, new_username)
    assert response.status_code == 200
    assert response.json()["username"] == new_username
    stored = await crud.user.get_by_username(db_session=async_session, username=new_username)
    assert stored is not None
    assert stored.email == user_data["email"]


async def test_update_username_to_taken_name_conflicts(async_client, async_session) -> None:
    headers, _ = await create_isolated_user_with_token(async_client, async_session)
    other_data = create_fake_user()
    await crud.user.create(db_session=async_session, obj_in=UserCreate(**other_data))
    response = await _put_username(async_client, headers, other_data["username"])
    assert response.status_code == 409


@pytest.mark.parametrize("username", ["ab", "x" * 33])
async def test_update_username_rejects_out_of_bounds_value(async_client, async_session, username) -> None:
    headers, _ = await create_isolated_user_with_token(async_client, async_session)
    response = await _put_username(async_client, headers, username)
    assert response.status_code == 400
    assert "3 and 32" in response.json()["detail"]


async def test_username_change_is_rate_limited(async_client, async_session) -> None:
    headers, _ = await create_isolated_user_with_token(async_client, async_session)
    first = await _put_username(async_client, headers, f"nyx_{uuid4().hex[:8]}")
    assert first.status_code == 200
    second = await _put_username(async_client, headers, f"nyx_{uuid4().hex[:8]}")
    assert second.status_code == 429
    assert "can be changed again" in second.json()["detail"]


async def test_username_change_allowed_after_cooldown(async_client, async_session) -> None:
    headers, user_data = await create_isolated_user_with_token(async_client, async_session)
    user = await crud.user.get_by_email(db_session=async_session, email=user_data["email"])
    assert user is not None
    user.username_changed_at = utcnow() - timedelta(days=settings.USERNAME_CHANGE_COOLDOWN_DAYS + 1)
    await async_session.commit()
    response = await _put_username(async_client, headers, f"nyx_{uuid4().hex[:8]}")
    assert response.status_code == 200


async def test_resubmitting_the_same_username_is_not_rate_limited(async_client, async_session) -> None:
    headers, _ = await create_isolated_user_with_token(async_client, async_session)
    username = f"nyx_{uuid4().hex[:8]}"
    assert (await _put_username(async_client, headers, username)).status_code == 200
    assert (await _put_username(async_client, headers, username)).status_code == 200


async def test_username_conflict_from_lost_race_returns_409(async_client, async_session) -> None:
    headers, _ = await create_isolated_user_with_token(async_client, async_session)
    other = await crud.user.create(db_session=async_session, obj_in=UserCreate(**create_fake_user()))
    with patch("app.services.user_service.crud.user.get_by_username", new=AsyncMock(return_value=None)):
        response = await _put_username(async_client, headers, other.username)
    assert response.status_code == 409
    assert "already taken" in response.json()["detail"]
