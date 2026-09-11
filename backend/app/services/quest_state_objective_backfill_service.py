"""Repair legacy state objectives that were started as timed quests."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerStatusEnum
from app.crud.dweller import dweller as dweller_crud
from app.crud.quest import quest_crud
from app.crud.quest_party import quest_party_crud


class QuestStateObjectiveBackfillService:
    """Convert started state objectives to their immediate-completion model."""

    async def backfill_started_state_objectives(self, db_session: AsyncSession) -> int:
        """Release parties and make started building/population/training objectives claimable."""
        links = await quest_crud.get_started_state_objective_links(db_session)

        for link in links:
            for member in await quest_party_crud.get_party_for_quest(db_session, link.quest_id, link.vault_id):
                if dweller := await dweller_crud.get_or_none(db_session, member.dweller_id, include_deleted=True):
                    dweller.status = DwellerStatusEnum.IDLE
                await db_session.delete(member)
            link.started_at = None
            link.duration_minutes = None
            link.is_reward_ready = True

        if links:
            await db_session.commit()
        return len(links)


quest_state_objective_backfill_service = QuestStateObjectiveBackfillService()
