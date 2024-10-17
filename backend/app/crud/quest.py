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


quest_crud = CRUDQuest(Quest, VaultQuestCompletionLink)
