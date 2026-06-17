import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import UUID4
from sqlalchemy.orm import selectinload
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
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

    async def get_available_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, skip: int = 0, limit: int = 100
    ) -> list[Quest]:
        """Get quests available for a vault, respecting quest chain prerequisites."""
        completed_result = await db_session.execute(
            select(VaultQuestCompletionLink.quest_id).where(
                and_(
                    VaultQuestCompletionLink.vault_id == vault_id,
                    VaultQuestCompletionLink.is_completed == True,
                )
            )
        )
        completed_quest_ids = set(completed_result.scalars().all())

        result = await db_session.execute(
            select(Quest)
            .options(selectinload(Quest.quest_requirements), selectinload(Quest.quest_rewards))
            .join(
                VaultQuestCompletionLink,
                and_(Quest.id == VaultQuestCompletionLink.quest_id, VaultQuestCompletionLink.vault_id == vault_id),
            )
            .where(VaultQuestCompletionLink.is_visible == True)
        )
        all_quests = result.scalars().all()

        available = []
        for quest in all_quests:
            if quest.previous_quest_id is None or quest.previous_quest_id in completed_quest_ids:
                available.append(quest)

        return available[skip : skip + limit]

    async def complete_quest_and_free_party(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4
    ) -> tuple[Quest, list[Any]]:
        """Complete a quest and set party dwellers back to idle."""
        from app.crud.quest_party import quest_party_crud

        quest, granted_rewards = await crud.quest_crud.complete(
            db_session=db_session, quest_entity_id=quest_id, vault_id=vault_id
        )

        party = await quest_party_crud.get_party_for_quest(db_session, quest_id, vault_id)
        for member in party:
            dweller = await db_session.get(Dweller, member.dweller_id)
            if dweller:
                dweller.status = "idle"
        await db_session.commit()

        return quest, granted_rewards

    async def get_eligible_dwellers(
        self, db_session: AsyncSession, vault_id: UUID4, quest_id: UUID4
    ) -> list[dict[str, Any]]:
        """Get dwellers eligible for a quest based on requirements."""
        from app.utils.exceptions import ResourceNotFoundException

        quest = await db_session.get(Quest, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)

        await db_session.refresh(quest, ["quest_requirements"])

        result = await db_session.execute(
            select(Dweller).where(Dweller.vault_id == vault_id, Dweller.is_deleted == False)
        )
        dwellers = result.scalars().all()

        vault_level_req_types = {"item", "room", "dweller_count", "quest_completed"}
        eligible = []
        for dweller in dwellers:
            meets_req = True
            for req in quest.quest_requirements:
                req_type = req.requirement_type
                req_data = req.requirement_data or {}

                if req_type == "level":
                    required_level = req_data.get("level", 1)
                    if dweller.level < required_level:
                        meets_req = False
                        break
                elif req_type in vault_level_req_types:
                    pass
                else:
                    meets_req = False
                    break

            if meets_req:
                eligible.append(
                    {
                        "id": str(dweller.id),
                        "first_name": dweller.first_name,
                        "last_name": dweller.last_name,
                        "level": dweller.level,
                        "rarity": dweller.rarity,
                    }
                )

        return eligible


quest_service = QuestService()
