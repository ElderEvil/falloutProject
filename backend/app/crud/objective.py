from collections.abc import Sequence

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.objective import ObjectiveCreate, ObjectiveRead, ObjectiveUpdate


class CRUDObjective(
    CRUDBase[Objective, ObjectiveCreate, ObjectiveUpdate],
):
    def __init__(self, model: type[Objective], link_model: type[VaultObjectiveProgressLink]):
        super().__init__(model)
        self.link_model = link_model

    async def create_for_vault(self, db_session: AsyncSession, vault_id: UUID4, obj_in: ObjectiveCreate) -> Objective:
        db_obj = self.model(**obj_in.model_dump())
        db_session.add(db_obj)

        link_obj = self.link_model(vault_id=vault_id, objective_id=db_obj.id)
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


objective_crud = CRUDObjective(Objective, VaultObjectiveProgressLink)
