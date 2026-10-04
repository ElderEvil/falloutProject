"""Tests for persisted quest completion details (completed_at + granted_rewards)."""

from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_reward import QuestReward, RewardType
from app.models.vault import Vault
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.common import AgeGroupEnum
from app.schemas.quest import QuestCreate
from app.services.progression.quests.service import quest_service
from app.services.team_service import team_service
from app.tests.factory.dwellers import create_fake_dweller


async def _expired_quest(
    async_session: AsyncSession,
    vault: Vault,
    *,
    duration_minutes: int = 60,
    reward_amount: int | None = 50,
) -> tuple[Quest, VaultQuestCompletionLink, Dweller]:
    """A started quest whose work window has elapsed, with a party assigned."""
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Completion Persistence Quest",
            short_description="Persist completion",
            long_description="A returned party whose completion details must persist.",
            requirements="One adult dweller",
            rewards="50 caps",
            duration_minutes=duration_minutes,
        ),
    )
    if reward_amount is not None:
        async_session.add(
            QuestReward(
                quest_id=quest.id,
                reward_type=RewardType.CAPS,
                reward_data={"amount": reward_amount},
                reward_chance=1.0,
            )
        )
    link = await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    dweller_data = create_fake_dweller()
    dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller = Dweller(**dweller_data, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
    await quest_service.start_quest(async_session, quest.id, vault.id)
    await async_session.refresh(link)
    link.started_at = datetime.utcnow() - timedelta(minutes=duration_minutes + 1)
    link.duration_minutes = duration_minutes
    await async_session.commit()
    return quest, link, dweller


async def _ready_to_claim(async_session: AsyncSession, quest: Quest, link: VaultQuestCompletionLink) -> None:
    """Drive a quest through its return leg until its rewards are claimable."""
    await quest_service.start_quest_return(async_session, quest.id, link.vault_id)
    await async_session.refresh(link)
    link.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    await async_session.commit()
    await quest_service.mark_quest_ready_to_claim(async_session, quest.id, link.vault_id)
    await async_session.refresh(link)


@pytest.mark.asyncio
async def test_claim_persists_completed_at_and_granted_rewards(async_session: AsyncSession, vault: Vault) -> None:
    """Claiming stamps completed_at and records the settled caps reward on the link."""
    quest, link, dweller = await _expired_quest(async_session, vault)
    await _ready_to_claim(async_session, quest, link)

    await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)

    await async_session.refresh(link)
    assert link.completed_at is not None
    assert {"reward_type": "caps", "amount": 50} in link.granted_rewards


@pytest.mark.asyncio
async def test_completed_at_none_before_claim(async_session: AsyncSession, vault: Vault) -> None:
    """A quest that is ready to claim is not completed until the claim commits."""
    quest, link, dweller = await _expired_quest(async_session, vault)
    await _ready_to_claim(async_session, quest, link)

    await async_session.refresh(link)
    assert link.is_reward_ready is True
    assert link.completed_at is None
    assert link.granted_rewards is None


@pytest.mark.asyncio
async def test_claim_without_rewards_persists_xp_only(async_session: AsyncSession, vault: Vault) -> None:
    """A reward-less quest still records its XP-only settlement on the link."""
    quest, link, dweller = await _expired_quest(async_session, vault, reward_amount=None)
    await _ready_to_claim(async_session, quest, link)

    await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)

    await async_session.refresh(link)
    assert link.completed_at is not None
    assert link.granted_rewards is not None
    assert [reward["reward_type"] for reward in link.granted_rewards] == ["experience"]
