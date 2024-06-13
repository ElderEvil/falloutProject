from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.crud.mixins import CompletionMixin
from app.models.quest import Quest, QuestChain, QuestObjective
from app.models.vault_quests import (
    VaultQuestChainCompletionLink,
    VaultQuestCompletionLink,
    VaultQuestObjectiveCompletionLink,
)
from app.schemas.quest import (
    QuestChainCreate,
    QuestChainJSON,
    QuestChainUpdate,
    QuestCreate,
    QuestObjectiveCreate,
    QuestObjectiveUpdate,
    QuestUpdate,
)


class CRUDQuestChain(
    CRUDBase[QuestChain, QuestChainCreate, QuestChainUpdate], CompletionMixin[VaultQuestChainCompletionLink]
):
    async def _handle_completion_cascade(
        self, *, db_session: AsyncSession, db_obj: QuestObjective, vault_id: UUID4
    ) -> None:
        pass

    async def insert_quest_chain(self, db_session: AsyncSession, quest_chain_data: QuestChainJSON):
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

            await objective_crud.create_all(db_session, objectives_create)


class CRUDQuest(CRUDBase[Quest, QuestCreate, QuestUpdate], CompletionMixin[VaultQuestCompletionLink]):
    async def _handle_completion_cascade(
        self, db_session: AsyncSession, db_obj: QuestObjective, vault_id: UUID4
    ) -> None:
        quest_chain = await quest_chain_crud.get(db_session, db_obj.quest_chain_id)
        if quest_chain and all(quest.is_completed for quest in quest_chain.quests):
            await quest_chain_crud.complete(db_session=db_session, obj_id=quest_chain.id, vault_id=vault_id)


class CRUDObjective(
    CRUDBase[QuestObjective, QuestObjectiveCreate, QuestObjectiveUpdate],
    CompletionMixin[VaultQuestObjectiveCompletionLink],
):
    async def _handle_completion_cascade(self, db_session: AsyncSession, db_obj: QuestChain, vault_id: UUID4) -> None:
        quest = await quest_crud.get(db_session, db_obj.quest_id)
        if quest and all(obj.is_completed for obj in quest.objectives):
            await quest_crud.complete(db_session=db_session, obj_id=quest.id, vault_id=vault_id)


quest_chain_crud = CRUDQuestChain(QuestChain)
quest_crud = CRUDQuest(Quest)
objective_crud = CRUDObjective(QuestObjective)
