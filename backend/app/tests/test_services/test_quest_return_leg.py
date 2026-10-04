"""Tests for the quest return leg (parties travel home before rewards)."""

from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum
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
from app.utils.exceptions import ValidationException


async def _expired_quest(
    async_session: AsyncSession, vault: Vault, *, duration_minutes: int = 60
) -> tuple[Quest, VaultQuestCompletionLink, Dweller]:
    """A started quest whose work window has elapsed, with a party assigned."""
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Return Leg Quest",
            short_description="Travel home",
            long_description="A party that must travel home before rewards.",
            requirements="One adult dweller",
            rewards="50 caps",
            duration_minutes=duration_minutes,
        ),
    )
    async_session.add(
        QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 50}, reward_chance=1.0)
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


@pytest.mark.asyncio
async def test_return_starts_at_expiry(async_session: AsyncSession, vault: Vault) -> None:
    """An elapsed quest starts its return leg; the party stays QUESTING."""
    quest, link, dweller = await _expired_quest(async_session, vault)

    completed = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)

    assert completed == 0
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    assert link.return_started_at is not None
    assert link.return_completes_at is not None
    assert link.is_reward_ready is False
    assert link.is_completed is False
    assert dweller.status == DwellerStatusEnum.QUESTING


@pytest.mark.asyncio
async def test_mark_ready_refuses_while_travelling(async_session: AsyncSession, vault: Vault) -> None:
    """A party still travelling home cannot be marked ready to claim."""
    quest, link, dweller = await _expired_quest(async_session, vault)
    await quest_service.start_quest_return(async_session, quest.id, vault.id)

    with pytest.raises(ValidationException, match="still travelling home"):
        await quest_service.mark_quest_ready_to_claim(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_start_return_refuses_before_expiry(async_session: AsyncSession, vault: Vault) -> None:
    """A quest still in its work window cannot start its return leg."""
    quest, link, dweller = await _expired_quest(async_session, vault)
    link.started_at = datetime.utcnow() - timedelta(minutes=10)
    link.duration_minutes = 60
    await async_session.commit()

    with pytest.raises(ValidationException, match="still in progress"):
        await quest_service.start_quest_return(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_start_return_refuses_when_already_returning(async_session: AsyncSession, vault: Vault) -> None:
    """A party already travelling home cannot start a second return leg."""
    quest, link, dweller = await _expired_quest(async_session, vault)
    await quest_service.start_quest_return(async_session, quest.id, vault.id)

    with pytest.raises(ValidationException, match="already travelling home"):
        await quest_service.start_quest_return(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_arrival_finalizes_once_and_is_idempotent(async_session: AsyncSession, vault: Vault) -> None:
    """Arrival flips the party to IDLE and makes rewards claimable exactly once."""
    quest, link, dweller = await _expired_quest(async_session, vault)
    await quest_service.start_quest_return(async_session, quest.id, vault.id)
    await async_session.refresh(link)
    link.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    await async_session.commit()

    await quest_service.mark_quest_ready_to_claim(async_session, quest.id, vault.id)
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    assert link.is_reward_ready is True
    assert dweller.status == DwellerStatusEnum.IDLE

    await quest_service.mark_quest_ready_to_claim(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_rewards_unclaimable_while_travelling(async_session: AsyncSession, vault: Vault) -> None:
    """Claiming while the party travels home is rejected."""
    quest, link, dweller = await _expired_quest(async_session, vault)
    await quest_service.start_quest_return(async_session, quest.id, vault.id)

    with pytest.raises(ValidationException, match="not ready to claim"):
        await quest_service.claim_quest_rewards(async_session, quest.id, vault.id)


@pytest.mark.asyncio
async def test_existing_no_window_quest_gets_a_return_leg(async_session: AsyncSession, vault: Vault) -> None:
    """A pre-migration quest without return fields gets a return window on the next tick."""
    quest, link, dweller = await _expired_quest(async_session, vault)
    link.return_started_at = None
    link.return_completes_at = None
    await async_session.commit()

    completed = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)

    assert completed == 0
    await async_session.refresh(link)
    assert link.return_completes_at is not None
    assert link.is_reward_ready is False


@pytest.mark.asyncio
async def test_state_objective_quests_skip_the_return_leg(async_session: AsyncSession, vault: Vault) -> None:
    """Building/population/training quests stay instantly ready, no travel window."""
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Building objective",
            short_description="Reach the objective",
            long_description="The vault already meets this objective.",
            requirements="Existing vault progress",
            rewards="100 caps",
            quest_category="building",
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    link = await quest_service.start_quest(async_session, quest.id, vault.id)
    assert link.is_reward_ready is True
    assert link.started_at is None

    completed = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)

    assert completed == 0
    await async_session.refresh(link)
    assert link.is_reward_ready is True
    assert link.return_completes_at is None


@pytest.mark.asyncio
async def test_tick_starts_return_then_finalizes_on_arrival(async_session: AsyncSession, vault: Vault) -> None:
    """check_and_complete_quests starts the return leg, then finalizes on arrival."""
    quest, link, dweller = await _expired_quest(async_session, vault)

    first = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)
    assert first == 0
    await async_session.refresh(link)
    assert link.return_completes_at is not None
    assert link.is_reward_ready is False

    link.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    await async_session.commit()

    second = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)
    assert second == 1
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    assert link.is_reward_ready is True
    assert dweller.status == DwellerStatusEnum.IDLE
