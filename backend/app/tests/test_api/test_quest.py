from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

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


async def _vault_with_quest(async_session: AsyncSession, client, **quest_fields):
    """A vault with one quest assigned to its owner, plus that owner's auth headers."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    quest = await crud.quest_crud.create(async_session, obj_in=QuestCreate(**quest_fields))
    headers = await user_authentication_headers(client=client, email=user.email, password=user_data["password"])
    return vault, quest, headers


async def test_start_accepts_and_departs_selected_party(async_client, async_session: AsyncSession) -> None:
    vault, quest, headers = await _vault_with_quest(
        async_session,
        async_client,
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


async def test_vault_quest_list_serializes_return_leg_and_completion_details(async_client, async_session) -> None:
    vault, quest, headers = await _vault_with_quest(
        async_session,
        async_client,
        title="Returning Serialization",
        short_description="ETA fields",
        long_description="The list read must expose the return ETA and the completion details.",
        requirements="None",
        rewards="50 caps",
        duration_minutes=60,
    )
    completed = await crud.quest_crud.create(
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
    now = utcnow()
    async_session.add_all(
        [
            VaultQuestCompletionLink(
                vault_id=vault.id,
                quest_id=quest.id,
                is_visible=True,
                started_at=now - timedelta(minutes=120),
                duration_minutes=60,
                return_started_at=now - timedelta(minutes=10),
                return_completes_at=now + timedelta(minutes=20),
            ),
            VaultQuestCompletionLink(
                vault_id=vault.id,
                quest_id=completed.id,
                is_visible=True,
                is_completed=True,
                completed_at=now,
                granted_rewards=[{"reward_type": "caps", "amount": 50}],
            ),
        ]
    )
    await async_session.commit()
    response = await async_client.get(f"/quests/{vault.id}/", headers=headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    by_id = {row["id"]: row for row in response.json()}
    assert by_id[str(quest.id)]["return_started_at"] is not None
    assert by_id[str(quest.id)]["return_completes_at"] is not None
    assert by_id[str(completed.id)]["completed_at"] is not None
    assert by_id[str(completed.id)]["granted_rewards"] == [{"reward_type": "caps", "amount": 50}]


async def test_assign_returns_the_completion_link_wire_shape(async_client, async_session: AsyncSession) -> None:
    vault, quest, headers = await _vault_with_quest(
        async_session,
        async_client,
        title="Assign Serialization",
        short_description="Assign fields",
        long_description="The assignment response is the vault link itself.",
        requirements="None",
        rewards="None",
        duration_minutes=60,
    )
    response = await async_client.post(f"/quests/{vault.id}/{quest.id}/assign", headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "vault_id",
        "quest_id",
        "is_completed",
        "is_reward_ready",
        "is_visible",
        "started_at",
        "duration_minutes",
        "return_started_at",
        "return_completes_at",
        "completed_at",
        "granted_rewards",
    }
    assert body["vault_id"] == str(vault.id)
    assert body["is_visible"] is True


async def test_superuser_create_update_delete_quest_template_round_trip(
    async_client, async_session: AsyncSession, superuser_token_headers
) -> None:
    vault_id = uuid4()
    payload = {
        "title": "Admin Template",
        "short_description": "Template CRUD",
        "long_description": "Create, update and delete a global quest template.",
        "requirements": "None",
        "rewards": "None",
        "duration_minutes": 60,
    }
    created = await async_client.post(f"/quests/{vault_id}/", json=payload, headers=superuser_token_headers)
    assert created.status_code == 200, created.text
    quest_id = UUID(created.json()["id"])

    updated = await async_client.put(
        f"/quests/{vault_id}/{quest_id}",
        params={"_vault_id": str(vault_id)},
        json=payload | {"title": "Admin Template Updated"},
        headers=superuser_token_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Admin Template Updated"

    deleted = await async_client.delete(
        f"/quests/{vault_id}/{quest_id}",
        params={"_vault_id": str(vault_id)},
        headers=superuser_token_headers,
    )
    assert deleted.status_code == 204, deleted.text
    assert await crud.quest_crud.get_or_none(async_session, quest_id) is None
