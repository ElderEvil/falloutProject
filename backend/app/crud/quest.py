import logging
from collections.abc import Sequence
from typing import Any

from pydantic import UUID4
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.crud.mixins import CompletionMixin
from app.crud.vault_mixin import VaultActionsMixin
from app.models import Vault
from app.models.quest import Quest
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import QuestCreate, QuestRead, QuestUpdate
from app.services.notification_service import notification_service
from app.services.reward_service import reward_service
from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)


class CRUDQuest(
    CRUDBase[Quest, QuestCreate, QuestUpdate], VaultActionsMixin[Vault], CompletionMixin[VaultQuestCompletionLink]
):
    def __init__(self, model: type[Quest], link_model: type[VaultQuestCompletionLink]):
        super().__init__(model)
        self.link_model = link_model

    async def get_multi_for_vault(
        self, *, db_session: AsyncSession, skip: int, limit: int, vault_id: UUID4
    ) -> Sequence[QuestRead]:
        """
        Get all quests assigned to a vault with their completion status.
        """
        query = (
            select(
                Quest,
                self.link_model.is_visible,
                self.link_model.is_completed,
            )
            .join(self.link_model)
            .where(self.link_model.vault_id == vault_id)
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        results = response.all()

        return [
            QuestRead(
                id=quest.id,
                title=quest.title,
                short_description=quest.short_description,
                long_description=quest.long_description,
                requirements=quest.requirements,
                rewards=quest.rewards,
                created_at=quest.created_at,
                updated_at=quest.updated_at,
                is_visible=is_visible,
                is_completed=is_completed,
            )
            for quest, is_visible, is_completed in results
        ]

    @staticmethod
    async def create_quest(db_session: AsyncSession, quest_data: QuestCreate) -> Quest:
        quest = Quest(
            title=quest_data.title,
            description=quest_data.description,
            short_description=quest_data.short_description,
            long_description=quest_data.long_description,
            requirements=quest_data.requirements,
            rewards=quest_data.rewards,
        )
        db_session.add(quest)
        await db_session.commit()
        await db_session.refresh(quest)
        return quest

    async def _handle_completion_cascade(self, db_session: AsyncSession, db_obj: Quest, vault_id: UUID4) -> None:
        """Grant rewards when a quest is completed."""
        from app.services.event_bus import GameEvent, event_bus

        granted_rewards: list[dict[str, Any]] = []

        # Grant rewards
        try:
            granted_rewards = await reward_service.process_quest_rewards(db_session, vault_id, db_obj)
            if granted_rewards:
                reward_summary = ", ".join(
                    f"{r.get('amount', r.get('name', r.get('dweller_id', '?')))}" for r in granted_rewards
                )
                logger.info(f"Granted rewards for quest '{db_obj.title}': {reward_summary}")
        except Exception:
            logger.exception(f"Failed to grant rewards for quest '{db_obj.title}'")

        # Emit quest completed event (even if reward processing failed)
        await event_bus.emit(
            GameEvent.QUEST_COMPLETED,
            vault_id,
            {"quest_id": str(db_obj.id), "quest_title": db_obj.title},
        )

        # Send notification
        try:
            vault = await db_session.get(Vault, vault_id)
            if vault and vault.user_id:
                await notification_service.notify_quest_completed(
                    db_session, vault.user_id, vault_id, db_obj.title, granted_rewards
                )
        except Exception:
            logger.exception(f"Failed to send quest completion notification for '{db_obj.title}'")

    async def assign_to_vault(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4, *, is_visible: bool = True
    ) -> VaultQuestCompletionLink:
        """
        Assign a quest to a vault, making it available for completion.

        Args:
            db_session: Database session
            quest_id: ID of the quest to assign
            vault_id: ID of the vault to assign the quest to
            is_visible: Whether the quest should be visible (default: True)

        Returns:
            VaultQuestCompletionLink: The created link between vault and quest
        """
        # Check if quest exists
        quest = await self.get(db_session, quest_id)
        if not quest:
            raise ResourceNotFoundException(Quest, identifier=quest_id)

        # Check if link already exists
        existing_link_query = select(self.link_model).where(
            and_(self.link_model.vault_id == vault_id, self.link_model.quest_id == quest_id)
        )
        result = await db_session.execute(existing_link_query)
        existing_link = result.scalar_one_or_none()

        if existing_link:
            # Update visibility if link exists
            existing_link.is_visible = is_visible
            await db_session.commit()
            await db_session.refresh(existing_link)
            return existing_link

        # Create new link
        link = self.link_model(vault_id=vault_id, quest_id=quest_id, is_visible=is_visible, is_completed=False)
        db_session.add(link)
        await db_session.commit()
        await db_session.refresh(link)
        return link


quest_crud = CRUDQuest(Quest, VaultQuestCompletionLink)
