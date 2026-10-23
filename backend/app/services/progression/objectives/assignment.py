import logging
import random
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ObjectiveCategoryEnum
from app.core.event_bus import GameEvent, event_bus
from app.crud.objective import objective_crud
from app.crud.vault import vault as vault_crud
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.guidance import current_state_progress

logger = logging.getLogger(__name__)


def _earned(link: VaultObjectiveProgressLink) -> bool:
    return link.is_completed or link.progress >= link.total


class ObjectiveAssignmentService:
    DAILY_COUNT = 3
    WEEKLY_COUNT = 7

    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session
        self._pending_completions: list[dict[str, Any]] = []

    async def assign_daily_objectives(self, vault_id: UUID4) -> list[Objective]:
        return await self._assign_category_objectives(vault_id, ObjectiveCategoryEnum.DAILY, self.DAILY_COUNT)

    async def assign_weekly_objectives(self, vault_id: UUID4) -> list[Objective]:
        return await self._assign_category_objectives(vault_id, ObjectiveCategoryEnum.WEEKLY, self.WEEKLY_COUNT)

    async def assign_achievement_objectives(self, vault_id: UUID4, *, auto_commit: bool = True) -> list[Objective]:
        """Assign first stages and reconcile legacy links, preserving earned rewards."""
        db = self._db_session
        self._pending_completions = []
        await vault_crud.lock_for_update(db, vault_id)
        templates = await objective_crud.get_assignable_achievements(db)
        links = {link.objective_id: link for link in await objective_crud.get_links_for_vault(db, vault_id)}
        tracks: dict[str, list[Objective]] = {}
        for objective in templates:
            tracks.setdefault(objective.track_key or str(objective.id), []).append(objective)
        assigned = []
        for stages in tracks.values():
            # Legacy vaults continue from their oldest assigned unfinished stage.
            # A newer, easier catalog stage is not retroactively rewarded.
            present = [o for o in stages if o.id in links]
            # An earned-but-unclaimed stage stays active: the next stage must not
            # unlock (or count) until this reward is collected.
            unclaimed = [o for o in present if not links[o.id].is_completed]
            if unclaimed:
                active = unclaimed[0]
            elif present:
                last_claimed = max((o.sequence or 0 for o in present if links[o.id].is_completed), default=0)
                active = next((o for o in stages if (o.sequence or 0) > last_claimed), None)
            else:
                active = stages[0]
            for objective in present:
                link = links[objective.id]
                if not _earned(link):
                    if objective is active and link.is_locked:
                        link.progress = 0
                        link.credited_dweller_ids = []
                        link.reward_snapshot = None
                    link.is_locked = objective is not active
            if active is not None and active.id not in links:
                link = VaultObjectiveProgressLink(vault_id=vault_id, objective_id=active.id, total=active.target_amount)
                db.add(link)
                if active.objective_type == "reach":
                    link.progress = min(link.total, await current_state_progress(db, vault_id, active))
                    if link.progress >= link.total:
                        self._pending_completions.append(await self.prepare_completion(vault_id, active, link))
                assigned.append(active)
        await db.flush()
        if auto_commit:
            await db.commit()
            await self.notify_completions(vault_id)
        return assigned

    async def prepare_completion(
        self, vault_id: UUID4, objective: Objective, link: VaultObjectiveProgressLink
    ) -> dict[str, Any]:
        """Freeze the reward and unlock a stage in the caller's transaction."""
        link.progress = objective.target_amount
        link.reward_snapshot = link.reward_snapshot or objective.reward
        # The next achievement stage unlocks only when this reward is claimed.
        return {
            "objective_id": str(objective.id),
            "challenge": objective.challenge,
            "ready_to_claim": True,
        }

    async def notify_completions(self, vault_id: UUID4) -> None:
        """Publish initial-assignment completions only after the caller commits."""
        completions, self._pending_completions = self._pending_completions, []
        for data in completions:
            await event_bus.emit(GameEvent.OBJECTIVE_COMPLETED, vault_id, data)

    async def unlock_next_achievement(self, vault_id: UUID4, completed: Objective) -> Objective | None:
        """Unlock the next unfinished stage at zero in the completion transaction."""
        db = self._db_session
        if not completed.track_key:
            return None
        stages = [
            o
            for o in await objective_crud.get_assignable_achievements(db)
            if o.track_key == completed.track_key and (o.sequence or 0) > (completed.sequence or 0)
        ]
        links = {link.objective_id: link for link in await objective_crud.get_links_for_vault(db, vault_id)}
        for objective in stages:
            link = links.get(objective.id)
            if link is not None and link.is_completed:
                continue
            if link is not None and not link.is_locked:
                return None  # Already unlocked; its own claim advances the chain.
            if link is None:
                db.add(
                    VaultObjectiveProgressLink(
                        vault_id=vault_id, objective_id=objective.id, total=objective.target_amount
                    )
                )
            elif link.is_locked:
                link.is_locked = False
                link.progress = 0
                link.total = objective.target_amount
                link.credited_dweller_ids = []
                link.reward_snapshot = None
            else:
                return None  # Already unlocked; duplicate completion must not reset progress.
            await db.flush()
            return objective
        return None

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

    async def refresh_daily_objectives(self, vault_id: UUID4, *, auto_commit: bool = True) -> list[Objective]:
        return await self._refresh_category_objectives(
            vault_id, ObjectiveCategoryEnum.DAILY, self.DAILY_COUNT, auto_commit
        )

    async def refresh_weekly_objectives(self, vault_id: UUID4, *, auto_commit: bool = True) -> list[Objective]:
        return await self._refresh_category_objectives(
            vault_id, ObjectiveCategoryEnum.WEEKLY, self.WEEKLY_COUNT, auto_commit
        )

    async def _refresh_category_objectives(
        self, vault_id: UUID4, category: ObjectiveCategoryEnum, count: int, auto_commit: bool
    ) -> list[Objective]:
        await self._clear_category_objectives(vault_id, category, auto_commit=False)
        await self._db_session.flush()
        assigned = await self._assign_category_objectives(vault_id, category, count, auto_commit=False)
        if auto_commit:
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
                total=objective.target_amount or 1,
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
            if link.objective_id in category_objective_ids and (link.is_completed or link.progress < link.total)
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
                total=objective.target_amount or 1,
            )
            self._db_session.add(link)

        assigned = unassigned[:count]
        if assigned:
            await self._db_session.commit()
            logger.info(f"Assigned {len(assigned)} random objectives to vault {vault_id}")
        return assigned
