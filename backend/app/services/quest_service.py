import logging
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.quest import Quest
from app.models.vault_quest import VaultQuestCompletionLink

logger = logging.getLogger(__name__)


class QuestService:
    async def check_and_complete_quests(self, db_session: AsyncSession) -> int:
        """Check for quests that have exceeded their duration and auto-complete them."""
        now = datetime.now()

        query = (
            select(VaultQuestCompletionLink)
            .join(Quest)
            .where(
                VaultQuestCompletionLink.is_completed == False,
                VaultQuestCompletionLink.started_at.isnot(None),
            )
        )
        result = await db_session.execute(query)
        links = result.scalars().all()

        completed_count = 0
        for link in links:
            duration = link.duration_minutes or 60
            if link.started_at and now >= link.started_at + timedelta(minutes=duration):
                link.is_completed = True
                completed_count += 1
                logger.info(f"Auto-completed quest {link.quest_id} for vault {link.vault_id}")

        if completed_count > 0:
            await db_session.commit()

        return completed_count

    async def start_quest(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4, duration_minutes: int | None = None
    ) -> VaultQuestCompletionLink:
        """Start a quest with a timer."""
        from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException

        query = select(VaultQuestCompletionLink).where(
            and_(
                VaultQuestCompletionLink.quest_id == quest_id,
                VaultQuestCompletionLink.vault_id == vault_id,
            )
        )
        result = await db_session.execute(query)
        link = result.scalar_one_or_none()

        if not link:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )

        if link.is_completed:
            raise AccessDeniedException("Quest already completed")

        link.started_at = datetime.now()
        if duration_minutes is not None:
            link.duration_minutes = duration_minutes

        await db_session.commit()
        await db_session.refresh(link)

        logger.info(
            f"Started quest {quest_id} for vault {vault_id} with duration {duration_minutes or 'default'} minutes"
        )
        return link


quest_service = QuestService()
