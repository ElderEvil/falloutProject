"""Repair legacy state objectives that were started as timed quests."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerStatusEnum
from app.crud.dweller import dweller as dweller_crud
from app.crud.quest import quest_crud
from app.crud.team import team_crud


class QuestStateObjectiveBackfillService:
    """Convert started state objectives to their immediate-completion model."""

    async def backfill_started_state_objectives(self, db_session: AsyncSession) -> int:
        """Release teams and make started building/population/training objectives claimable."""
        links = await quest_crud.get_started_state_objective_links(db_session)

        for link in links:
            for member in await team_crud.get_quest_team(db_session, link.quest_id, link.vault_id):
                if dweller := await dweller_crud.get_or_none(db_session, member.dweller_id, include_deleted=True):
                    dweller.status = DwellerStatusEnum.IDLE
            await team_crud.delete_quest_team(db_session, link.quest_id, link.vault_id)
            link.started_at = None
            link.duration_minutes = None
            link.is_reward_ready = True

        if links:
            await db_session.commit()
        return len(links)


quest_state_objective_backfill_service = QuestStateObjectiveBackfillService()
