from collections.abc import Sequence

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.objective import ObjectiveCreate, ObjectiveUpdate


class CRUDObjective(
    CRUDBase[Objective, ObjectiveCreate, ObjectiveUpdate],
):
    def __init__(self, model: type[Objective], link_model: type[VaultObjectiveProgressLink]):
        super().__init__(model)
        self.link_model = link_model

    async def get_multi_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, skip: int = 0, limit: int = 100
    ) -> Sequence[Objective]:
        query = (
            select(self.model)
            .join(self.link_model)
            .where(
                self.link_model.vault_id == vault_id,
            )
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()


objective_crud = CRUDObjective(Objective, VaultObjectiveProgressLink)
