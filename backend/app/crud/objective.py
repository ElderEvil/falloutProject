import contextlib
import logging
from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.objective import ObjectiveCreate, ObjectiveRead, ObjectiveUpdate

logger = logging.getLogger(__name__)


class CRUDObjective(CRUDBase[Objective, ObjectiveCreate, ObjectiveUpdate]):
    def __init__(self, model: type[Objective], link_model: type[VaultObjectiveProgressLink]):
        """Configure objective persistence with its vault-progress link model."""
        super().__init__(model)
        self.link_model = link_model

    async def create_for_vault(self, db_session: AsyncSession, vault_id: UUID4, obj_in: ObjectiveCreate) -> Objective:
        """Create an objective together with its initial vault progress link."""
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
        """Return a vault's objectives with their persisted progress state."""
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
                category=obj.category,
                objective_type=obj.objective_type,
                target_entity=obj.target_entity,
                target_amount=obj.target_amount,
                progress=progress,
                total=total,
                is_completed=is_completed,
            )
            for obj, progress, total, is_completed in results
        ]

    async def get_by_category(self, db_session: AsyncSession, category: str) -> list[Objective]:
        """All objectives of one category."""
        result = await db_session.execute(select(self.model).where(self.model.category == category))
        return list(result.scalars().all())

    async def get_all(self, db_session: AsyncSession) -> list[Objective]:
        """Every objective."""
        return list((await db_session.execute(select(self.model))).scalars().all())

    async def get_assigned_objective_ids(self, db_session: AsyncSession, vault_id: UUID4) -> set[UUID4]:
        """IDs of objectives already linked to the vault."""
        result = await db_session.execute(
            select(self.link_model.objective_id).where(self.link_model.vault_id == vault_id)
        )
        return {row[0] for row in result.all()}

    async def get_links_for_vault(self, db_session: AsyncSession, vault_id: UUID4) -> list[VaultObjectiveProgressLink]:
        """All progress links of a vault."""
        return list(
            (await db_session.execute(select(self.link_model).where(self.link_model.vault_id == vault_id))).scalars()
        )

    async def delete_links(self, db_session: AsyncSession, links: Sequence[VaultObjectiveProgressLink]) -> None:
        """Delete the given progress links without committing."""
        for link in links:
            await db_session.delete(link)

    async def link_exists(self, db_session: AsyncSession, *, vault_id: UUID4, objective_id: UUID4) -> bool:
        """Whether the vault already has a progress link for the objective."""
        result = await db_session.execute(
            select(self.link_model).where(
                self.link_model.vault_id == vault_id,
                self.link_model.objective_id == objective_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_active_with_links(
        self, db_session: AsyncSession, vault_id: UUID4, objective_type: str
    ) -> list[tuple[Objective, VaultObjectiveProgressLink]]:
        """(objective, link) pairs of unfinished vault objectives of one objective_type."""
        query = (
            select(self.model, self.link_model)
            .join(self.link_model)
            .where(
                self.link_model.vault_id == vault_id,
                self.link_model.is_completed.is_(False),
                self.model.objective_type == objective_type,
            )
        )
        return list((await db_session.execute(query)).all())

    async def assign_initial(self, db_session: AsyncSession, vault_id: UUID4, *, is_boosted: bool) -> int:
        """Assign the deterministic starter objective set for a new vault."""
        try:
            categories = ["daily", "weekly"]
            objectives = [
                (
                    await db_session.execute(
                        select(self.model)
                        .where(col(self.model.category) == category, col(self.model.objective_type).is_not(None))
                        .order_by(col(self.model.id))
                        .limit(1)
                    )
                ).scalar_one_or_none()
                for category in categories
            ]
            if is_boosted:
                result = await db_session.execute(
                    select(self.model)
                    .where(
                        col(self.model.category).not_in(categories),
                        col(self.model.objective_type).is_not(None),
                    )
                    .order_by(col(self.model.id))
                    .limit(8)
                )
                objectives.extend(result.scalars().all())
            links = [
                self.link_model(
                    vault_id=vault_id,
                    objective_id=objective.id,
                    progress=0,
                    total=objective.target_amount,
                    is_completed=False,
                )
                for objective in objectives
                if objective
            ]
            for link in links:
                db_session.add(link)
            if links:
                await db_session.commit()
            return len(links)
        except SQLAlchemyError:
            logger.exception("Failed to assign initial objectives to vault %s", vault_id)
            with contextlib.suppress(Exception):
                await db_session.rollback()
            return 0

    async def get_link_for_update(
        self, db_session: AsyncSession, objective_id: UUID4, vault_id: UUID4
    ) -> VaultObjectiveProgressLink | None:
        """Lock an objective link before deciding whether it can be completed."""
        result = await db_session.execute(
            select(self.link_model)
            .where(self.link_model.vault_id == vault_id, self.link_model.objective_id == objective_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_multi_complete(
        self, db_session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[Objective]:
        """Get objectives with all required fields for completion tracking.

        Complete objectives have:
        - objective_type is not None
        - target_entity is not None (can be None for some types like assign)
        - target_amount >= 1
        """
        query = (
            select(self.model)
            .where(self.model.objective_type.is_not(None))
            .where(self.model.target_entity.is_not(None))
            .where(self.model.target_amount > 1)
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()


objective_crud = CRUDObjective(Objective, VaultObjectiveProgressLink)
