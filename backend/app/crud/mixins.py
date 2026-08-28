from contextlib import suppress
from typing import Any, TypeVar

from pydantic import UUID4
from sqlmodel import SQLModel, and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException

LinkModelType = TypeVar("LinkModelType", bound=SQLModel)
ModelType = TypeVar("ModelType", bound=SQLModel)


class CompletionMixin[LinkModelType]:
    link_model: type[LinkModelType]

    async def get_link(self, *, db_session: AsyncSession, vault_id: UUID4, quest_entity_id: UUID4) -> LinkModelType:
        query = select(self.link_model).where(
            and_(self.link_model.vault_id == vault_id, self.link_model.quest_id == quest_entity_id)
        )
        result = await db_session.execute(query)
        quest_completion_link = result.scalar_one_or_none()

        if not quest_completion_link:
            raise ResourceNotFoundException(self.link_model, identifier=quest_entity_id)
        if quest_completion_link.is_completed:
            raise ResourceConflictException("Already completed")

        return quest_completion_link

    async def _mark_as_complete(
        self, *, db_session: AsyncSession, quest_entity_id: UUID4, vault_id: UUID4
    ) -> LinkModelType:
        """Lock and claim a completion link before any rewards are delivered."""
        query = (
            select(self.link_model)
            .where(and_(self.link_model.vault_id == vault_id, self.link_model.quest_id == quest_entity_id))
            .with_for_update()
        )
        result = await db_session.execute(query)
        quest_completion_link = result.scalar_one_or_none()
        if quest_completion_link is None:
            raise ResourceNotFoundException(self.link_model, identifier=quest_entity_id)
        if quest_completion_link.is_completed:
            raise ResourceConflictException("Already completed")
        quest_completion_link.is_completed = True

        return quest_completion_link

    async def _handle_completion_cascade(
        self,
        *,
        db_session: AsyncSession,
        db_obj: LinkModelType,
        vault_id: UUID4,
    ) -> list[dict[str, Any]]:
        msg = "Subclasses must implement this method"
        raise NotImplementedError(msg)

    async def _after_completion_commit(
        self,
        *,
        db_session: AsyncSession,
        db_obj: LinkModelType,
        vault_id: UUID4,
        granted_rewards: list[dict[str, Any]],
    ) -> None:
        """Run completion side effects only after the completion is durable."""

    async def complete(
        self, *, db_session: AsyncSession, quest_entity_id: UUID4, vault_id: UUID4
    ) -> tuple[Any, list[dict[str, Any]]]:
        db_obj = None
        try:
            db_obj = await self.get(db_session, quest_entity_id)
            await self._mark_as_complete(db_session=db_session, vault_id=vault_id, quest_entity_id=quest_entity_id)
            granted_rewards = await self._handle_completion_cascade(
                db_session=db_session, db_obj=db_obj, vault_id=vault_id
            )
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            if db_obj is not None:
                with suppress(Exception):
                    await db_session.refresh(db_obj)
            raise

        await self._after_completion_commit(
            db_session=db_session,
            db_obj=db_obj,
            vault_id=vault_id,
            granted_rewards=granted_rewards,
        )

        return db_obj, granted_rewards
