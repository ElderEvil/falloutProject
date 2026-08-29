import logging
from datetime import datetime, timedelta
from typing import Any

from pydantic import UUID4
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum

logger = logging.getLogger(__name__)


class QuestService:
    async def check_and_complete_quests(self, db_session: AsyncSession, vault_id: UUID4 | None = None) -> int:
        """Mark elapsed quests ready for reward claiming and return their parties."""
        now = datetime.now()
        duration_minutes = func.coalesce(VaultQuestCompletionLink.duration_minutes, Quest.duration_minutes)
        if db_session.bind and db_session.bind.dialect.name == "sqlite":
            expires_at = func.datetime(
                VaultQuestCompletionLink.started_at,
                func.printf("+%s minutes", duration_minutes),
            )
        else:
            expires_at = VaultQuestCompletionLink.started_at + func.make_interval(0, 0, 0, 0, 0, duration_minutes)

        conditions = [
            ~VaultQuestCompletionLink.is_completed,
            ~VaultQuestCompletionLink.is_reward_ready,
            VaultQuestCompletionLink.started_at.isnot(None),
            expires_at <= now,
        ]
        if vault_id is not None:
            conditions.append(VaultQuestCompletionLink.vault_id == vault_id)
        query = select(VaultQuestCompletionLink).join(Quest).where(*conditions)
        result = await db_session.execute(query)
        links = [(link.quest_id, link.vault_id) for link in result.scalars().all()]

        completed_count = 0
        for quest_id, link_vault_id in links:
            try:
                await self.mark_quest_ready_to_claim(db_session, quest_id, link_vault_id)
            except Exception:
                logger.exception(f"Failed to auto-complete quest {quest_id} for vault {link_vault_id}")
            else:
                completed_count += 1
                logger.info(f"Quest {quest_id} is ready to claim for vault {link_vault_id}")

        return completed_count

    async def start_quest(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> VaultQuestCompletionLink:
        """Start a quest with a timer."""
        from app.crud.quest_party import quest_party_crud
        from app.utils.exceptions import (
            AccessDeniedException,
            ResourceConflictException,
            ResourceNotFoundException,
            ValidationException,
        )

        query = select(VaultQuestCompletionLink).where(
            and_(
                VaultQuestCompletionLink.quest_id == quest_id,
                VaultQuestCompletionLink.vault_id == vault_id,
            )
        )
        link = (await db_session.execute(query)).scalars().one_or_none()

        if not link:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )

        if link.is_completed:
            raise AccessDeniedException("Quest already completed")
        if link.started_at is not None:
            raise ResourceConflictException("Quest is already in progress")

        quest = await db_session.get(Quest, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        if quest.duration_minutes is None or quest.duration_minutes <= 0:
            raise ValidationException("Quest duration must be a positive value")

        party = await quest_party_crud.get_party_for_quest(db_session, quest_id, vault_id)
        if not party:
            raise ValidationException("Assign at least one dweller before starting this quest")

        link.started_at = datetime.now()
        link.is_reward_ready = False
        link.duration_minutes = quest.duration_minutes

        await db_session.commit()
        await db_session.refresh(link)

        logger.info(f"Started quest {quest_id} for vault {vault_id} with duration {link.duration_minutes} minutes")
        return link

    async def get_available_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, skip: int = 0, limit: int = 100
    ) -> list[Quest]:
        """Get quests available for a vault, respecting quest chain prerequisites."""
        completed_result = await db_session.execute(
            select(VaultQuestCompletionLink.quest_id).where(
                and_(
                    VaultQuestCompletionLink.vault_id == vault_id,
                    VaultQuestCompletionLink.is_completed,
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
            .where(VaultQuestCompletionLink.is_visible)
        )
        all_quests = result.scalars().all()

        available = [
            quest
            for quest in all_quests
            if quest.previous_quest_id is None or quest.previous_quest_id in completed_quest_ids
        ]

        return available[skip : skip + limit]

    async def mark_quest_ready_to_claim(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> Quest:
        """Return a finished party and make its rewards available to claim."""
        from app.crud.quest_party import quest_party_crud
        from app.utils.exceptions import ResourceNotFoundException, ValidationException

        link = (
            (
                await db_session.execute(
                    select(VaultQuestCompletionLink).where(
                        VaultQuestCompletionLink.quest_id == quest_id,
                        VaultQuestCompletionLink.vault_id == vault_id,
                    )
                )
            )
            .scalars()
            .one_or_none()
        )
        if link is None:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )
        if link.started_at is None:
            raise ValidationException("Quest must be started before it can be completed")

        quest = await db_session.get(Quest, quest_id)
        if quest is None:
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        duration = link.duration_minutes if link.duration_minutes is not None else quest.duration_minutes
        if datetime.now() < link.started_at + timedelta(minutes=duration):
            raise ValidationException("Quest is still in progress")
        if link.is_reward_ready:
            return quest

        party = await quest_party_crud.get_party_for_quest(db_session, quest_id, vault_id)
        for member in party:
            dweller = await db_session.get(Dweller, member.dweller_id)
            if dweller:
                dweller.status = DwellerStatusEnum.IDLE
        link.is_reward_ready = True
        await db_session.commit()

        return quest

    async def claim_quest_rewards(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4
    ) -> tuple[Quest, list[Any]]:
        """Atomically deliver rewards that a returning party has made claimable."""
        from app.utils.exceptions import ResourceNotFoundException, ValidationException

        link = (
            (
                await db_session.execute(
                    select(VaultQuestCompletionLink).where(
                        VaultQuestCompletionLink.quest_id == quest_id,
                        VaultQuestCompletionLink.vault_id == vault_id,
                    )
                )
            )
            .scalars()
            .one_or_none()
        )
        if link is None:
            raise ResourceNotFoundException(
                VaultQuestCompletionLink, identifier=f"quest {quest_id} for vault {vault_id}"
            )
        if not link.is_reward_ready:
            raise ValidationException("Quest rewards are not ready to claim")

        return await crud.quest_crud.complete(db_session=db_session, quest_entity_id=quest_id, vault_id=vault_id)

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
            select(Dweller).where(
                Dweller.vault_id == vault_id,
                ~Dweller.is_deleted,
                Dweller.is_adult,
                Dweller.age_group == AgeGroupEnum.ADULT,
                Dweller.status.notin_([DwellerStatusEnum.QUESTING, DwellerStatusEnum.EXPLORING]),
            )
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
