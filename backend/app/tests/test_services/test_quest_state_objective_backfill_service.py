import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum
from app.models.quest import Quest
from app.models.team import Team, TeamMember
from app.models.vault_quest import VaultQuestCompletionLink
from app.services.quest_state_objective_backfill_service import quest_state_objective_backfill_service
from app.utils.time import utcnow


def _new_quest(**kw) -> dict:
    base = {
        "title": "Build a Room",
        "short_description": "Build your first room.",
        "long_description": "Build a Living Quarter for your dwellers.",
        "requirements": "1 Living Quarter",
        "rewards": "100 caps",
    }
    return base | kw


async def _scalars(async_session: AsyncSession, statement):
    return (await async_session.execute(statement)).scalars().all()


async def test_backfill_retires_legacy_state_objective_party(async_session: AsyncSession, vault, dweller) -> None:
    quest = Quest(**_new_quest(quest_category="building"))
    async_session.add(quest)
    await async_session.commit()
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    # Legacy data predates the state-objective party guard, so seed the team directly.
    team = Team(vault_id=vault.id, quest_id=quest.id)
    async_session.add(team)
    await async_session.flush()
    async_session.add(TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=1, status="assigned"))
    dweller.status = DwellerStatusEnum.QUESTING
    await async_session.commit()
    link = await async_session.get(VaultQuestCompletionLink, (vault.id, quest.id))
    assert link is not None
    link.started_at = utcnow()
    link.duration_minutes = 60
    await async_session.commit()
    assert await quest_state_objective_backfill_service.backfill_started_state_objectives(async_session) == 1
    await async_session.refresh(link)
    await async_session.refresh(dweller)
    membership = (Team.vault_id == vault.id, Team.quest_id == quest.id)
    members = await _scalars(async_session, select(TeamMember).join(Team).where(*membership))
    teams = await _scalars(async_session, select(Team).where(*membership))
    assert (link.is_reward_ready, link.started_at, link.duration_minutes, members, teams, dweller.status) == (
        True,
        None,
        None,
        [],
        [],
        DwellerStatusEnum.IDLE,
    )
    assert await quest_state_objective_backfill_service.backfill_started_state_objectives(async_session) == 0
