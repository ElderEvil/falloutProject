from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy.orm import selectinload
from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.crud.mixins import CompletionMixin
from app.models.quest import Quest, QuestChain, QuestObjective
from app.models.vault_quest import (
    VaultQuestChainCompletionLink,
    VaultQuestCompletionLink,
    VaultQuestObjectiveCompletionLink,
)
from app.schemas.quest import (
    QuestChainCreate,
    QuestChainJSON,
    QuestChainReadWithQuests,
    QuestChainUpdate,
    QuestCreate,
    QuestObjectiveCreate,
    QuestObjectiveUpdate,
    QuestUpdate,
)


class CRUDQuestChain(
    CRUDBase[QuestChain, QuestChainCreate, QuestChainUpdate], CompletionMixin[VaultQuestChainCompletionLink]
):
    def __init__(self, model: type[QuestChain], link_model: type[VaultQuestChainCompletionLink]):
        super().__init__(model)
        self.link_model = link_model

    async def get_multi_for_vault(
        self, *, db_session: AsyncSession, skip: int, limit: int, vault_id: UUID4
    ) -> Sequence[QuestChainReadWithQuests]:
        """
        Get multiple not completed visible quest chains for a vault.
        """
        query = (
            select(QuestChain)
            .options(selectinload(QuestChain.quests))
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
        quest_chains = response.scalars().all()

        return [QuestChainReadWithQuests.model_validate(chain) for chain in quest_chains]

    async def _handle_completion_cascade(
        self, *, db_session: AsyncSession, db_obj: QuestObjective, vault_id: UUID4
    ) -> None:
        pass

    @staticmethod
    async def insert_quest_chain(db_session: AsyncSession, quest_chain_data: QuestChainJSON):
        # Create the quest chain
        quest_chain_create = QuestChainCreate(title=quest_chain_data.title)
        quest_chain = await quest_chain_crud.create(db_session, quest_chain_create)

        for quest_data in quest_chain_data.quests:
            # Create each quest
            quest_create = QuestCreate(
                title=quest_data.quest_name,
                description=quest_data.long_description,
                short_description=quest_data.short_description,
                long_description=quest_data.long_description,
                requirements=str(quest_data.requirements),
                rewards=quest_data.rewards,
                chain_id=quest_chain.id,
            )
            quest = await quest_crud.create(db_session, quest_create)

            # Create the quest objective
            objectives_create = [
                QuestObjectiveCreate(title=quest_objective.title, quest_id=quest.id)
                for quest_objective in quest_data.quest_objective
            ]

            await quest_objective_crud.create_all(db_session, objectives_create)


class CRUDQuest(CRUDBase[Quest, QuestCreate, QuestUpdate], CompletionMixin[VaultQuestCompletionLink]):
    def __init__(self, model: type[Quest], link_model: type[VaultQuestCompletionLink]):
        super().__init__(model)
        self.link_model = link_model

    async def _handle_completion_cascade(
        self, db_session: AsyncSession, db_obj: QuestObjective, vault_id: UUID4
    ) -> None:
        # TODO: Implement this method
        pass


class CRUDQuestObjective(
    CRUDBase[QuestObjective, QuestObjectiveCreate, QuestObjectiveUpdate],
    CompletionMixin[VaultQuestObjectiveCompletionLink],
):
    def __init__(self, model: type[QuestObjective], link_model: type[VaultQuestObjectiveCompletionLink]):
        super().__init__(model)
        self.link_model = link_model

    async def _handle_completion_cascade(
        self, db_session: AsyncSession, db_obj: QuestObjective, vault_id: UUID4
    ) -> None:
        # TODO: Implement this method
        pass


quest_chain_crud = CRUDQuestChain(QuestChain, VaultQuestChainCompletionLink)
quest_crud = CRUDQuest(Quest, VaultQuestCompletionLink)
quest_objective_crud = CRUDQuestObjective(QuestObjective, VaultQuestObjectiveCompletionLink)
