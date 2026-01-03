from collections.abc import Sequence

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
from app.utils.exceptions import ResourceNotFoundException


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
        Get multiple not completed visible quests for a vault.
        """
        query = (
            select(Quest)
            .join(self.link_model)
            .where(
                and_(
                    self.link_model.vault_id == vault_id,
                    self.link_model.is_visible == True,
                    self.link_model.is_completed == False,
                )
            )
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        quests = response.scalars().all()

        return [QuestRead.model_validate(quest) for quest in quests]

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
        # Implement any cascading logic here if needed
        pass

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
