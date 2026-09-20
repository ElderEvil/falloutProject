"""Quest endpoint tests — error mapping for reward claims."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException


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
async def test_claim_quest_rewards_twice_returns_409(
    async_client,
    superuser_token_headers: dict[str, str],
) -> None:
    """A second claim of an already-completed quest is rejected, never re-settled."""
    vault_id = uuid4()
    quest_id = uuid4()

    with (
        patch(
            "app.api.v1.endpoints.quest.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.quest.quest_service.claim_quest_rewards",
            AsyncMock(side_effect=ResourceConflictException("Already completed")),
        ),
    ):
        response = await async_client.post(
            f"/quests/{vault_id}/{quest_id}/claim-rewards",
            headers=superuser_token_headers,
        )
    assert response.status_code == 409
    assert "Already completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_claim_quest_rewards_before_ready_returns_400(
    async_client,
    superuser_token_headers: dict[str, str],
) -> None:
    """Claiming a quest whose rewards are not ready is a client error, not a 404."""
    vault_id = uuid4()
    quest_id = uuid4()

    with (
        patch(
            "app.api.v1.endpoints.quest.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.quest.quest_service.claim_quest_rewards",
            AsyncMock(side_effect=ValidationException("Quest rewards are not ready to claim")),
        ),
    ):
        response = await async_client.post(
            f"/quests/{vault_id}/{quest_id}/claim-rewards",
            headers=superuser_token_headers,
        )
    assert response.status_code == 400
    assert "not ready to claim" in response.json()["detail"]
