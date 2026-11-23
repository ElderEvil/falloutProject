from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import QuestCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.rooms import create_overseers_office
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.tests.utils.user import user_authentication_headers
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.quest_duration import effective_quest_duration_minutes
from app.utils.time import utcnow

CLAIM_PATCH = "app.api.v1.endpoints.quest"


async def _vault_with_quest(async_session: AsyncSession, **quest_fields):
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    quest = await crud.quest_crud.create(async_session, obj_in=QuestCreate(**quest_fields))
    return user_data, user, vault, quest


async def test_start_accepts_and_departs_selected_party(async_client, async_session: AsyncSession) -> None:
    user_data, user, vault, quest = await _vault_with_quest(
        async_session,
        title="Atomic Departure",
        short_description="Depart",
        long_description="Select and depart together",
        requirements="None",
        rewards="None",
        duration_minutes=60,
    )
    office = Room(**create_overseers_office(tier=2), vault_id=vault.id)
    dweller = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add_all([office, dweller])
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])
    response = await async_client.post(
        f"/quests/{vault.id}/{quest.id}/start", json={"dweller_ids": [str(dweller.id)]}, headers=headers
    )
    assert response.status_code == 200, response.text
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.QUESTING
    members = await crud.team_crud.get_quest_team(async_session, quest.id, vault.id)
    assert [member.dweller_id for member in members] == [dweller.id]
    link = await crud.quest_crud.get_link(async_session, quest_id=quest.id, vault_id=vault.id)
    assert link.started_at is not None
    assert link.duration_minutes == effective_quest_duration_minutes(60, office_tier=2)


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (ResourceConflictException("Storage full for vault"), 409, "Storage full"),
        (ResourceConflictException("Already completed"), 409, "Already completed"),
        (ValidationException("Quest rewards are not ready to claim"), 400, "not ready to claim"),
        (ValidationException("Party is still travelling home"), 400, "still travelling home"),
    ],
)
async def test_claim_quest_rewards_rejects_unready_claims(
    async_client, superuser_token_headers, error, status, detail
) -> None:
    vault_id, quest_id = uuid4(), uuid4()
    with (
        patch(f"{CLAIM_PATCH}.get_user_vault_or_403", AsyncMock(return_value=None)),
        patch(f"{CLAIM_PATCH}.quest_service.claim_quest_rewards", AsyncMock(side_effect=error)),
    ):
        response = await async_client.post(
            f"/quests/{vault_id}/{quest_id}/claim-rewards", headers=superuser_token_headers
        )
    assert response.status_code == status
    assert detail in response.json()["detail"]


async def test_vault_quest_list_serializes_return_leg_fields(async_client, async_session: AsyncSession) -> None:
    user_data, user, vault, quest = await _vault_with_quest(
        async_session,
        title="Returning Serialization",
        short_description="ETA fields",
        long_description="The list read must expose the return ETA.",
        requirements="None",
        rewards="None",
        duration_minutes=60,
    )
    async_session.add(
        VaultQuestCompletionLink(
            vault_id=vault.id,
            quest_id=quest.id,
            is_visible=True,
            started_at=utcnow() - timedelta(minutes=120),
            duration_minutes=60,
            return_started_at=utcnow() - timedelta(minutes=10),
            return_completes_at=utcnow() + timedelta(minutes=20),
        )
    )
    await async_session.commit()
    headers = await user_authentication_headers(client=async_client, email=user.email, password=user_data["password"])
    response = await async_client.get(f"/quests/{vault.id}/", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    quest_read = next(q for q in response.json() if q["id"] == str(quest.id))
    assert quest_read["return_started_at"] is not None
    assert quest_read["return_completes_at"] is not None


async def test_vault_quest_list_serializes_completion_details(async_client, async_session: AsyncSession) -> None:
    user_data, user, vault, quest = await _vault_with_quest(
        async_session,
        title="Completion Serialization",
        short_description="Completion fields",
        long_description="The list read must expose the completion details.",
        requirements="None",
        rewards="50 caps",
        duration_minutes=60,
    )
    async_session.add(
        VaultQuestCompletionLink(
            vault_id=vault.id,
            quest_id=quest.id,
            is_visible=True,
            is_completed=True,
            completed_at=utcnow(),
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
