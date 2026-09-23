"""Quest endpoint tests — error mapping for reward claims."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import QuestCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.tests.utils.user import user_authentication_headers
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


@pytest.mark.asyncio
async def test_claim_quest_rewards_while_travelling_returns_400(
    async_client,
    superuser_token_headers: dict[str, str],
) -> None:
    """Claiming a quest whose party is still travelling home is a client error."""
    vault_id = uuid4()
    quest_id = uuid4()

    with (
        patch(
            "app.api.v1.endpoints.quest.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.quest.quest_service.claim_quest_rewards",
            AsyncMock(side_effect=ValidationException("Party is still travelling home")),
        ),
    ):
        response = await async_client.post(
            f"/quests/{vault_id}/{quest_id}/claim-rewards",
            headers=superuser_token_headers,
        )
    assert response.status_code == 400
    assert "still travelling home" in response.json()["detail"]


@pytest.mark.asyncio
async def test_vault_quest_list_serializes_return_leg_fields(
    async_client,
    async_session: AsyncSession,
) -> None:
    """The vault quest list exposes the return-leg ETA fields."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Returning Serialization",
            short_description="ETA fields",
            long_description="The list read must expose the return ETA.",
            requirements="None",
            rewards="None",
            duration_minutes=60,
        ),
    )
    async_session.add(
        VaultQuestCompletionLink(
            vault_id=vault.id,
            quest_id=quest.id,
            is_visible=True,
            started_at=datetime.utcnow() - timedelta(minutes=120),
            duration_minutes=60,
            return_started_at=datetime.utcnow() - timedelta(minutes=10),
            return_completes_at=datetime.utcnow() + timedelta(minutes=20),
        )
    )
    await async_session.commit()

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])
    response = await async_client.get(f"/quests/{vault.id}/", headers=headers)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    quest_read = next(q for q in response.json() if q["id"] == str(quest.id))
    assert quest_read["return_started_at"] is not None
    assert quest_read["return_completes_at"] is not None


@pytest.mark.asyncio
async def test_vault_quest_list_serializes_completion_details(
    async_client,
    async_session: AsyncSession,
) -> None:
    """The vault quest list exposes completed_at and granted_rewards."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Completion Serialization",
            short_description="Completion fields",
            long_description="The list read must expose the completion details.",
            requirements="None",
            rewards="50 caps",
            duration_minutes=60,
        ),
    )
    async_session.add(
        VaultQuestCompletionLink(
            vault_id=vault.id,
            quest_id=quest.id,
            is_visible=True,
            is_completed=True,
            completed_at=datetime.utcnow(),
            granted_rewards=[{"reward_type": "caps", "amount": 50}],
        )
    )
    await async_session.commit()

    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])
    response = await async_client.get(f"/quests/{vault.id}/", headers=headers)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    quest_read = next(q for q in response.json() if q["id"] == str(quest.id))
    assert quest_read["completed_at"] is not None
    assert quest_read["granted_rewards"] == [{"reward_type": "caps", "amount": 50}]
