from datetime import timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, RewardType
from app.models.dweller import Dweller
from app.models.quest_reward import QuestReward
from app.models.room import Room
from app.schemas.quest import QuestCreate
from app.services.progression.quests.service import quest_service
from app.services.team_service import team_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.rooms import create_overseers_office
from app.utils.exceptions import ValidationException
from app.utils.time import utcnow


def _quest_in(**kw) -> QuestCreate:
    base = {
        "title": "Return Leg Quest",
        "short_description": "Travel home",
        "long_description": "A party that must travel home before rewards.",
        "requirements": "One adult dweller",
        "rewards": "50 caps",
    }
    return QuestCreate(**(base | kw))


async def _expired_quest(async_session: AsyncSession, vault, *, duration_minutes: int = 60):
    quest = await crud.quest_crud.create(async_session, obj_in=_quest_in(duration_minutes=duration_minutes))
    async_session.add(
        QuestReward(quest_id=quest.id, reward_type=RewardType.CAPS, reward_data={"amount": 50}, reward_chance=1.0)
    )
    link = await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    dweller = Dweller(**create_fake_adult_dweller(), vault_id=vault.id)
    async_session.add_all([Room(**create_overseers_office(), vault_id=vault.id), dweller])
    await async_session.commit()
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [dweller.id])
    await quest_service.start_quest(async_session, quest.id, vault.id)
    await async_session.refresh(link)
    link.started_at = utcnow() - timedelta(minutes=duration_minutes + 1)
    link.duration_minutes = duration_minutes
    await async_session.commit()
    return quest, link, dweller


async def test_return_starts_at_expiry(async_session: AsyncSession, vault) -> None:
    _quest, link, dweller = await _expired_quest(async_session, vault)
    completed = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    assert completed == 0
    assert (link.return_started_at is not None, link.return_completes_at is not None) == (True, True)
    assert (link.is_reward_ready, link.is_completed, dweller.status) == (False, False, DwellerStatusEnum.QUESTING)


@pytest.mark.parametrize(
    ("method", "message"),
    [
        ("mark_quest_ready_to_claim", "still travelling home"),
        ("start_quest_return", "already travelling home"),
        ("claim_quest_rewards", "not ready to claim"),
    ],
)
async def test_refuses_while_travelling(async_session: AsyncSession, vault, method: str, message: str) -> None:
    quest, _link, _dweller = await _expired_quest(async_session, vault)
    await quest_service.start_quest_return(async_session, quest.id, vault.id)
    with pytest.raises(ValidationException, match=message):
        await getattr(quest_service, method)(async_session, quest.id, vault.id)


async def test_start_return_refuses_before_expiry(async_session: AsyncSession, vault) -> None:
    quest, link, _dweller = await _expired_quest(async_session, vault)
    link.started_at = utcnow() - timedelta(minutes=10)
    link.duration_minutes = 60
    await async_session.commit()
    with pytest.raises(ValidationException, match="still in progress"):
        await quest_service.start_quest_return(async_session, quest.id, vault.id)


async def test_arrival_finalizes_once_and_is_idempotent(async_session: AsyncSession, vault) -> None:
    quest, link, dweller = await _expired_quest(async_session, vault)
    await quest_service.start_quest_return(async_session, quest.id, vault.id)
    await async_session.refresh(link)
    link.return_completes_at = utcnow() - timedelta(seconds=1)
    await async_session.commit()
    await quest_service.mark_quest_ready_to_claim(async_session, quest.id, vault.id)
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    assert (link.is_reward_ready, dweller.status) == (True, DwellerStatusEnum.IDLE)
    await quest_service.mark_quest_ready_to_claim(async_session, quest.id, vault.id)


async def test_existing_no_window_quest_gets_a_return_leg(async_session: AsyncSession, vault) -> None:
    _quest, link, _dweller = await _expired_quest(async_session, vault)
    link.return_started_at = None
    link.return_completes_at = None
    await async_session.commit()
    completed = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)
    await async_session.refresh(link)
    assert completed == 0
    assert (link.return_completes_at is not None, link.is_reward_ready) == (True, False)


async def test_state_objective_quests_skip_the_return_leg(async_session: AsyncSession, vault) -> None:
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=_quest_in(title="Building objective", requirements="Existing vault progress", quest_category="building"),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    link = await quest_service.start_quest(async_session, quest.id, vault.id)
    assert (link.is_reward_ready, link.started_at) == (True, None)
    completed = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)
    await async_session.refresh(link)
    assert completed == 0
    assert (link.is_reward_ready, link.return_completes_at) == (True, None)


async def test_tick_starts_return_then_finalizes_on_arrival(async_session: AsyncSession, vault) -> None:
    _quest, link, dweller = await _expired_quest(async_session, vault)
    first = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)
    await async_session.refresh(link)
    assert first == 0
    assert (link.return_completes_at is not None, link.is_reward_ready) == (True, False)
    link.return_completes_at = utcnow() - timedelta(seconds=1)
    await async_session.commit()
    second = await quest_service.check_and_complete_quests(async_session, vault_id=vault.id)
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    assert second == 1
    assert (link.is_reward_ready, dweller.status) == (True, DwellerStatusEnum.IDLE)
