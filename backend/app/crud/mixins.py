from collections.abc import Sequence
from typing import Generic, TypeVar

from pydantic import UUID4
from sqlmodel import SQLModel, and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.utils.exceptions import ResourceNotFoundException

LinkModelType = TypeVar("LinkModelType", bound=SQLModel)
ModelType = TypeVar("ModelType", bound=SQLModel)


class CompletionMixin(Generic[LinkModelType]):
    link_model: type[LinkModelType]

    async def _get_all_quest_links_for_quest_chain(
        self, db_session: AsyncSession, quest_chain_id: UUID4, vault_id: UUID4
    ) -> Sequence[LinkModelType]:
        query = select(self.link_model).where(
            and_(self.link_model.vault_id == vault_id, self.link_model.quest_chain_id == quest_chain_id)
        )
        result = await db_session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def _get_all_objective_links_for_quest(
        db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4, link_model: type[LinkModelType]
    ) -> Sequence[LinkModelType]:
        query = select(link_model).where(and_(link_model.vault_id == vault_id, link_model.quest_entity_id == quest_id))
        result = await db_session.execute(query)
        return result.scalars().all()

    async def get_link(self, *, db_session: AsyncSession, vault_id: UUID4, quest_entity_id: UUID4) -> LinkModelType:
        query = select(self.link_model).where(
            and_(self.link_model.vault_id == vault_id, self.link_model.quest_entity_id == quest_entity_id)
        )
        result = await db_session.execute(query)
        quest_completion_link = result.scalar_one_or_none()

        if not quest_completion_link:
            raise ResourceNotFoundException(self.link_model, identifier=quest_entity_id)

        return quest_completion_link

    async def _mark_as_complete(
        self, *, db_session: AsyncSession, quest_entity_id: UUID4, vault_id: UUID4
    ) -> LinkModelType:
        quest_completion_link = await self.get_link(
            db_session=db_session, vault_id=vault_id, quest_entity_id=quest_entity_id
        )
        quest_completion_link.is_completed = True

        await db_session.commit()

        return quest_completion_link

    async def _handle_completion_cascade(
        self, *, db_session: AsyncSession, db_obj: LinkModelType, vault_id: UUID4
    ) -> None:
        raise NotImplementedError("Subclasses must implement this method")

    async def complete(self, *, db_session: AsyncSession, quest_entity_id: UUID4, vault_id: UUID4) -> LinkModelType:
        db_obj = await self.get(db_session, quest_entity_id)
        await self._mark_as_complete(db_session=db_session, vault_id=vault_id, quest_entity_id=quest_entity_id)
        await self._handle_completion_cascade(db_session=db_session, db_obj=db_obj, vault_id=vault_id)

        return db_obj
