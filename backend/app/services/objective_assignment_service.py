import logging
import random

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.common import ObjectiveCategoryEnum

logger = logging.getLogger(__name__)


class ObjectiveAssignmentService:
    DAILY_COUNT = 5
    WEEKLY_COUNT = 3

    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    async def assign_daily_objectives(self, vault_id: UUID4) -> list[Objective]:
        return await self._assign_category_objectives(vault_id, ObjectiveCategoryEnum.DAILY, self.DAILY_COUNT)

    async def assign_weekly_objectives(self, vault_id: UUID4) -> list[Objective]:
        return await self._assign_category_objectives(vault_id, ObjectiveCategoryEnum.WEEKLY, self.WEEKLY_COUNT)

    async def assign_achievement_objectives(self, vault_id: UUID4) -> list[Objective]:
        query = select(Objective).where(Objective.category == ObjectiveCategoryEnum.ACHIEVEMENT)
        result = await self._db_session.execute(query)
        all_achievements = list(result.scalars().all())

        assigned = []
        for objective in all_achievements:
            exists = await self._objective_already_assigned(vault_id, objective.id)
            if not exists:
                link = VaultObjectiveProgressLink(
                    vault_id=vault_id,
                    objective_id=objective.id,
                    progress=0,
                    total=objective.target_amount or 1,
                    is_completed=False,
                )
                self._db_session.add(link)
                assigned.append(objective)

        if assigned:
            await self._db_session.commit()
            logger.info(f"Assigned {len(assigned)} achievement objectives to vault {vault_id}")

        return assigned

    async def assign_all_objectives(self, vault_id: UUID4) -> dict[str, list[Objective]]:
        daily = await self.assign_daily_objectives(vault_id)
        weekly = await self.assign_weekly_objectives(vault_id)
        achievements = await self.assign_achievement_objectives(vault_id)

        return {
            "daily": daily,
            "weekly": weekly,
            "achievements": achievements,
        }

    async def clear_daily_objectives(self, vault_id: UUID4) -> int:
        return await self._clear_category_objectives(vault_id, ObjectiveCategoryEnum.DAILY)

    async def clear_weekly_objectives(self, vault_id: UUID4) -> int:
        return await self._clear_category_objectives(vault_id, ObjectiveCategoryEnum.WEEKLY)

    async def refresh_daily_objectives(self, vault_id: UUID4) -> list[Objective]:
        # Atomic clear + assign: do not commit between operations
        await self._clear_category_objectives(vault_id, ObjectiveCategoryEnum.DAILY, auto_commit=False)
        assigned = await self._assign_category_objectives(
            vault_id, ObjectiveCategoryEnum.DAILY, self.DAILY_COUNT, auto_commit=False
        )
        await self._db_session.commit()
        return assigned

    async def refresh_weekly_objectives(self, vault_id: UUID4) -> list[Objective]:
        # Atomic clear + assign: do not commit between operations
        await self._clear_category_objectives(vault_id, ObjectiveCategoryEnum.WEEKLY, auto_commit=False)
        assigned = await self._assign_category_objectives(
            vault_id, ObjectiveCategoryEnum.WEEKLY, self.WEEKLY_COUNT, auto_commit=False
        )
        await self._db_session.commit()
        return assigned

    async def _assign_category_objectives(
        self, vault_id: UUID4, category: ObjectiveCategoryEnum, count: int, auto_commit: bool = True
    ) -> list[Objective]:
        query = select(Objective).where(Objective.category == category)
        result = await self._db_session.execute(query)
        all_objectives = list(result.scalars().all())

        if not all_objectives:
            logger.warning(f"No {category} objectives found in database")
            return []

        # Fetch all assigned objective IDs in a single query to avoid N+1
        assigned_ids_query = select(VaultObjectiveProgressLink.objective_id).where(
            VaultObjectiveProgressLink.vault_id == vault_id
        )
        assigned_result = await self._db_session.execute(assigned_ids_query)
        assigned_ids = {row[0] for row in assigned_result.all()}

        available = [obj for obj in all_objectives if obj.id not in assigned_ids]

        selected = available if len(available) <= count else random.sample(available, count)

        assigned = []
        for objective in selected:
            link = VaultObjectiveProgressLink(
                vault_id=vault_id,
                objective_id=objective.id,
                progress=0,
                total=objective.target_amount or 1,
                is_completed=False,
            )
            self._db_session.add(link)
            assigned.append(objective)

        if assigned and auto_commit:
            await self._db_session.commit()
            logger.info(f"Assigned {len(assigned)} {category} objectives to vault {vault_id}")

        return assigned

    async def _clear_category_objectives(
        self, vault_id: UUID4, category: ObjectiveCategoryEnum, auto_commit: bool = True
    ) -> int:
        subquery = select(Objective.id).where(Objective.category == category)
        query = (
            select(VaultObjectiveProgressLink)
            .where(VaultObjectiveProgressLink.vault_id == vault_id)
            .where(VaultObjectiveProgressLink.objective_id.in_(subquery))
        )
        result = await self._db_session.execute(query)
        links = result.scalars().all()

        for link in links:
            await self._db_session.delete(link)

        if links and auto_commit:
            await self._db_session.commit()
            logger.info(f"Cleared {len(links)} {category} objectives for vault {vault_id}")

        return len(links)

    async def _objective_already_assigned(self, vault_id: UUID4, objective_id: UUID4) -> bool:
        query = select(VaultObjectiveProgressLink).where(
            VaultObjectiveProgressLink.vault_id == vault_id,
            VaultObjectiveProgressLink.objective_id == objective_id,
        )
        result = await self._db_session.execute(query)
        return result.scalar_one_or_none() is not None
