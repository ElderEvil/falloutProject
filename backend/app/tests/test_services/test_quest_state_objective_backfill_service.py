"""Regression coverage for legacy timed state-objective quests."""

from datetime import datetime

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.quest_party import quest_party_crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_party import QuestParty
from app.models.vault import Vault
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.common import DwellerStatusEnum
from app.services.quest_state_objective_backfill_service import quest_state_objective_backfill_service


@pytest.mark.asyncio
async def test_backfill_retires_legacy_state_objective_party(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A formerly timed building objective becomes party-free and claimable."""
    quest = Quest(
        title="Build a Room",
        short_description="Build your first room.",
        long_description="Build a Living Quarter for your dwellers.",
        requirements="1 Living Quarter",
        rewards="100 caps",
        quest_category="building",
    )
    async_session.add(quest)
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    await quest_party_crud.assign_party(async_session, quest.id, vault.id, [dweller.id])

    link = await async_session.get(VaultQuestCompletionLink, (vault.id, quest.id))
    assert link is not None
    link.started_at = datetime.utcnow()
    link.duration_minutes = 60
    await async_session.commit()

    assert await quest_state_objective_backfill_service.backfill_started_state_objectives(async_session) == 1
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    party = (
        (
            await async_session.execute(
                select(QuestParty).where(QuestParty.vault_id == vault.id, QuestParty.quest_id == quest.id)
            )
        )
        .scalars()
        .all()
    )
    assert (link.is_reward_ready, link.started_at, link.duration_minutes, party, dweller.status) == (
        True,
        None,
        None,
        [],
        DwellerStatusEnum.IDLE,
    )
    assert await quest_state_objective_backfill_service.backfill_started_state_objectives(async_session) == 0
