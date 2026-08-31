"""Repair legacy state objectives that were started as timed quests."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_party import QuestParty
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.common import DwellerStatusEnum


class QuestStateObjectiveBackfillService:
    """Convert started state objectives to their immediate-completion model."""

    async def backfill_started_state_objectives(self, db_session: AsyncSession) -> int:
        """Release parties and make started building/population/training objectives claimable."""
        result = await db_session.execute(
            select(VaultQuestCompletionLink)
            .join(Quest)
            .where(
                Quest.quest_category.in_(("building", "population", "training")),
                VaultQuestCompletionLink.started_at.is_not(None),
                ~VaultQuestCompletionLink.is_completed,
                ~VaultQuestCompletionLink.is_reward_ready,
            )
        )
        links = result.scalars().all()

        for link in links:
            party = await db_session.execute(
                select(QuestParty).where(
                    QuestParty.vault_id == link.vault_id,
                    QuestParty.quest_id == link.quest_id,
                )
            )
            for member in party.scalars():
                if dweller := await db_session.get(Dweller, member.dweller_id):
                    dweller.status = DwellerStatusEnum.IDLE
                await db_session.delete(member)
            link.started_at = None
            link.duration_minutes = None
            link.is_reward_ready = True

        if links:
            await db_session.commit()
        return len(links)


quest_state_objective_backfill_service = QuestStateObjectiveBackfillService()
