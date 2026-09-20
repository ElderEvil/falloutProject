import logging
import random

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ObjectiveCategoryEnum
from app.crud.objective import objective_crud
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink

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
        all_achievements = await objective_crud.get_by_category(self._db_session, ObjectiveCategoryEnum.ACHIEVEMENT)

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
        all_objectives = await objective_crud.get_by_category(self._db_session, category)

        if not all_objectives:
            logger.warning(f"No {category} objectives found in database")
            return []

        # Fetch all assigned objective IDs in a single query to avoid N+1
        assigned_ids = await objective_crud.get_assigned_objective_ids(self._db_session, vault_id)

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
        category_objective_ids = {o.id for o in await objective_crud.get_by_category(self._db_session, category)}
        links = [
            link
            for link in await objective_crud.get_links_for_vault(self._db_session, vault_id)
            if link.objective_id in category_objective_ids
        ]

        await objective_crud.delete_links(self._db_session, links)

        if links and auto_commit:
            await self._db_session.commit()
            logger.info(f"Cleared {len(links)} {category} objectives for vault {vault_id}")

        return len(links)

    async def assign_random_objectives(self, vault_id: UUID4, count: int = 5) -> list[Objective]:
        """Assign random unassigned objectives to a vault (testing/debugging)."""
        # Get all objective IDs already assigned to this vault
        assigned_ids = await objective_crud.get_assigned_objective_ids(self._db_session, vault_id)

        # Get all unassigned objectives
        all_objectives = await objective_crud.get_all(self._db_session)
        unassigned = [o for o in all_objectives if o.id not in assigned_ids]

        # Shuffle and assign up to 'count' objectives
        random.shuffle(unassigned)
        for objective in unassigned[:count]:
            link = VaultObjectiveProgressLink(
                vault_id=vault_id,
                objective_id=objective.id,
                progress=0,
                total=objective.target_amount or 1,
                is_completed=False,
            )
            self._db_session.add(link)

        assigned = unassigned[:count]
        if assigned:
            await self._db_session.commit()
            logger.info(f"Assigned {len(assigned)} random objectives to vault {vault_id}")
        return assigned

    async def _objective_already_assigned(self, vault_id: UUID4, objective_id: UUID4) -> bool:
        return await objective_crud.link_exists(self._db_session, vault_id=vault_id, objective_id=objective_id)
