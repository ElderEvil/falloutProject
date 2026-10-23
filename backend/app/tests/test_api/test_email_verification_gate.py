"""AI endpoints require a verified email address; chat stays available to everyone."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_verified_user
from app.tests.test_api.test_user import create_isolated_user_with_token
from app.utils.exceptions import AccessDeniedException

pytestmark = pytest.mark.asyncio(scope="module")

AI_ENDPOINTS = [
    ("generate_backstory/", {}, None),
    ("extend_bio/", {}, None),
    ("generate_visual_attributes/", {}, None),
    ("generate_photo/", {}, None),
    ("generate_audio/", {"text": "Hello"}, None),
    ("generate_with_ai/", {}, None),
    (
        "generate_avatar",
        {"dweller_first_name": "Test", "dweller_last_name": "User"},
        {"hair_color": "black"},
    ),
]


@pytest.mark.parametrize(("suffix", "params", "json_body"), AI_ENDPOINTS)
async def test_ai_endpoints_reject_unverified_users(
    async_client: AsyncClient,
    async_session: AsyncSession,
    suffix: str,
    params: dict[str, str],
    json_body: dict | None,
) -> None:
    """Every player-facing AI route answers 403 before touching a dweller or a provider."""
    headers, _ = await create_isolated_user_with_token(async_client, async_session)

    response = await async_client.post(
        f"/dwellers/{uuid4()}/{suffix}",
        params=params,
        json=json_body,
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Email verification required"


async def test_chat_endpoints_are_not_email_gated(
    async_client: AsyncClient,
    async_session: AsyncSession,
) -> None:
    """Unverified users still reach chat's own access checks instead of the AI gate."""
    headers, _ = await create_isolated_user_with_token(async_client, async_session)

    text_response = await async_client.post(f"/chat/{uuid4()}", json={"message": "Hi"}, headers=headers)
    history_response = await async_client.get(f"/chat/history/{uuid4()}", headers=headers)

    for response in (text_response, history_response):
        assert response.status_code == 404
        assert response.json()["detail"] != "Email verification required"


async def test_verified_dependency_rejects_unverified_user() -> None:
    with pytest.raises(AccessDeniedException, match="verification"):
        await get_current_verified_user(MagicMock(email_verified=False))


async def test_verified_dependency_allows_verified_user() -> None:
    user = MagicMock(email_verified=True)

    assert await get_current_verified_user(user) is user
