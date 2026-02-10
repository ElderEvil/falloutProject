from collections.abc import Sequence

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.crud.mixins import CompletionMixin
from app.models import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.objective import ObjectiveCreate, ObjectiveRead, ObjectiveUpdate


class CRUDObjective(
    CRUDBase[Objective, ObjectiveCreate, ObjectiveUpdate],
    CompletionMixin[VaultObjectiveProgressLink],
):
    def __init__(self, model: type[Objective], link_model: type[VaultObjectiveProgressLink]):
        super().__init__(model)
        self.link_model = link_model

    async def create_for_vault(self, db_session: AsyncSession, vault_id: UUID4, obj_in: ObjectiveCreate) -> Objective:
        db_obj = self.model(**obj_in.model_dump())
        db_session.add(db_obj)

        link_obj = self.link_model(
            vault_id=vault_id,
            objective_id=db_obj.id,
            total=obj_in.target_amount or 1,
        )
        db_session.add(link_obj)

        await db_session.commit()
        await db_session.refresh(link_obj)

        return db_obj

    async def get_multi_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, skip: int = 0, limit: int = 100
    ) -> Sequence[ObjectiveRead]:
        query = (
            select(self.model, self.link_model.progress, self.link_model.total, self.link_model.is_completed)
            .join(self.link_model)
            .where(self.link_model.vault_id == vault_id)
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        results = response.all()

        return [
            ObjectiveRead(
                id=obj.id,
                challenge=obj.challenge,
                reward=obj.reward,
                progress=progress,
                total=total,
                is_completed=is_completed,
            )
            for obj, progress, total, is_completed in results
        ]

    async def _handle_completion_cascade(self, db_session: AsyncSession, db_obj: Objective, vault_id: UUID4) -> None:
        """Handle any cascading logic when an objective is completed."""
        # Could trigger rewards, notifications, etc.

    async def complete(self, *, db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4) -> Objective:
        """
        Mark an objective as completed for a vault.

        Args:
            db_session: Database session
            objective_id: ID of the objective to complete
            vault_id: ID of the vault

        Returns:
            Completed objective
        """
        # Get the objective
        db_obj = await self.get(db_session, objective_id)

        # Get or create the link
        query = select(self.link_model).where(
            self.link_model.vault_id == vault_id, self.link_model.objective_id == objective_id
        )
        result = await db_session.execute(query)
        link = result.scalar_one_or_none()

        if not link:
            # Create new link if it doesn't exist
            link = self.link_model(vault_id=vault_id, objective_id=objective_id, progress=1, total=1, is_completed=True)
            db_session.add(link)
        else:
            # Mark as completed
            link.is_completed = True
            link.progress = link.total

        await db_session.commit()
        await self._handle_completion_cascade(db_session=db_session, db_obj=db_obj, vault_id=vault_id)

        return db_obj

    async def update_progress(
        self, db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4, progress: int
    ) -> VaultObjectiveProgressLink:
        """
        Update the progress of an objective for a vault.

        Args:
            db_session: Database session
            objective_id: ID of the objective
            vault_id: ID of the vault
            progress: New progress value

        Returns:
            Updated VaultObjectiveProgressLink
        """
        # Get or create the link
        query = select(self.link_model).where(
            self.link_model.vault_id == vault_id, self.link_model.objective_id == objective_id
        )
        result = await db_session.execute(query)
        link = result.scalar_one_or_none()

        if not link:
            # Get the objective to fetch target_amount
            objective = await self.get(db_session, objective_id)
            target_amount = objective.target_amount if objective else 1
            link = self.link_model(
                vault_id=vault_id,
                objective_id=objective_id,
                progress=progress,
                total=target_amount,
            )
            db_session.add(link)
        else:
            # Update progress
            link.progress = progress
            # Auto-complete if progress reaches total
            if link.progress >= link.total:
                link.is_completed = True

        await db_session.commit()
        await db_session.refresh(link)
        return link

    async def get_multi_complete(
        self, db_session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[Objective]:
        from sqlalchemy import text

        query = (
            select(self.model)
            .where(self.model.objective_type.is_not(None))
            .where(text("target_entity IS NOT NULL"))
            .where(self.model.target_amount > 1)
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()


objective_crud = CRUDObjective(Objective, VaultObjectiveProgressLink)
