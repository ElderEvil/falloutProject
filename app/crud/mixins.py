from select import select
from typing import Generic, TypeVar

from pydantic import UUID4
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.utils.exceptions import ResourceNotFoundException

ModelType = TypeVar("ModelType", bound=SQLModel)
VaultCompletionLinkType = TypeVar("VaultCompletionLinkType", bound=SQLModel)


class CompletionMixin(Generic[VaultCompletionLinkType]):
    def __init__(self, link_model: type[VaultCompletionLinkType]):
        self.link_model = link_model

    async def get_link(
        self, *, db_session: AsyncSession, vault_id: UUID4, quest_entity_id: UUID4
    ) -> VaultCompletionLinkType:
        link = await db_session.execute(
            select(self.link_model).filter_by(vault_id=vault_id, quest_entity_id=quest_entity_id)
        )
        quest_completion_link = link.scalar_one_or_none()

        if not quest_completion_link:
            raise ResourceNotFoundException(self.link_model, identifier=quest_entity_id)

        return quest_completion_link

    async def _mark_as_complete(
        self, *, db_session: AsyncSession, quest_entity_id: UUID4, vault_id: UUID4
    ) -> ModelType:
        quest_completion_link = await self.get_link(
            db_session=db_session, vault_id=vault_id, quest_entity_id=quest_entity_id
        )
        quest_completion_link.is_completed = True
        db_session.add(quest_completion_link)
        await db_session.commit()
        await db_session.refresh(quest_completion_link)

        return quest_completion_link

    async def _handle_completion_cascade(self, *, db_session: AsyncSession, db_obj: ModelType, vault_id: UUID4) -> None:
        raise NotImplementedError("Subclasses must implement this method")

    async def complete(self, *, db_session: AsyncSession, obj_id: UUID4, vault_id: UUID4) -> ModelType:
        db_obj = await self.get(db_session, obj_id)
        await self._mark_as_complete(db_session=db_session, vault_id=vault_id, quest_entity_id=obj_id)
        await self._handle_completion_cascade(db_session=db_session, db_obj=db_obj, vault_id=vault_id)

        return db_obj
