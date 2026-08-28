"""Quest endpoint tests — error mapping for reward claims."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


@pytest.mark.asyncio
async def test_claim_quest_rewards_storage_full_returns_409(
    async_client,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /quests/{vault_id}/{quest_id}/claim-rewards returns 409 when storage is full."""
    vault_id = uuid4()
    quest_id = uuid4()

    with (
        patch(
            "app.api.v1.endpoints.quest.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.quest.quest_service.claim_quest_rewards",
            AsyncMock(side_effect=ResourceConflictException("Storage full for vault")),
        ),
    ):
        response = await async_client.post(
            f"/quests/{vault_id}/{quest_id}/claim-rewards",
            headers=superuser_token_headers,
        )
    assert response.status_code == 409
    assert "Storage full" in response.json()["detail"]


@pytest.mark.asyncio
async def test_claim_quest_rewards_no_storage_returns_404(
    async_client,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /quests/{vault_id}/{quest_id}/claim-rewards returns 404 when no storage exists."""
    vault_id = uuid4()
    quest_id = uuid4()
    storage_model = MagicMock()
    storage_model.__name__ = "Storage"

    with (
        patch(
            "app.api.v1.endpoints.quest.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.quest.quest_service.claim_quest_rewards",
            AsyncMock(side_effect=ResourceNotFoundException(storage_model, vault_id)),
        ),
    ):
        response = await async_client.post(
            f"/quests/{vault_id}/{quest_id}/claim-rewards",
            headers=superuser_token_headers,
        )
    assert response.status_code == 404
    assert "Storage" in response.json()["detail"]
