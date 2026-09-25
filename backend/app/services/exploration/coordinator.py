"""Exploration coordinator - orchestrates exploration completion and recall."""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import dweller as dweller_crud
from app.crud import expedition_run as crud_expedition_run
from app.crud import exploration as crud_exploration
from app.crud import vault as crud_vault
from app.models.exploration import ExpeditionRunStatus, Exploration
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration.event_service import event_service
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration.rewards_service import rewards_service
from app.services.leveling_service import leveling_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# Error messages as constants to satisfy ruff
ERROR_NOT_ACTIVE = "Exploration is not active"
ERROR_NOT_RETURNING = "Exploration is not on the return leg"
ERROR_NOT_ARRIVED = "Exploration has not arrived home yet"


class ExplorationCoordinator:
    """Coordinates exploration completion and recall; events and rewards live in their own services."""

    async def start_return(
        self, db_session: AsyncSession, exploration_id: UUID4, *, recalled: bool = False
    ) -> Exploration:
        """Send a dweller home; rewards and loot wait until the return leg finishes.

        Args:
            db_session: Database session
            exploration_id: Exploration ID
            recalled: True for a player-initiated early recall, False for a natural finish

        Returns:
            Exploration: The exploration now in RETURNING state
        """
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError(ERROR_NOT_ACTIVE)
        if not recalled and exploration.time_remaining_seconds() > 0:
            raise ValueError("Exploration has not finished yet; recall the dweller to end it early")

        # Clock expiry and recall both force-retreat an open site run before the
        # return leg starts, all in this one transaction.
        run = await crud_expedition_run.get_open_for_exploration_for_update(db_session, exploration_id)
        if run is not None:
            run.status = ExpeditionRunStatus.RETREATED
            run.finished_at = datetime.utcnow()
            db_session.add(run)
            await db_session.flush()

        exploration = await crud_exploration.start_return(db_session, exploration_id=exploration_id, recalled=recalled)
        await db_session.commit()

        await event_service.publish_sse(
            exploration,
            "exploration_returning",
            recalled=recalled,
            return_started_at=exploration.return_started_at.isoformat() if exploration.return_started_at else None,
            return_completes_at=exploration.return_completes_at.isoformat()
            if exploration.return_completes_at
            else None,
        )

        return exploration

    async def finalize_return(self, db_session: AsyncSession, exploration_id: UUID4) -> RewardsSchema:
        """Finalize an arrived exploration: restore the dweller, release loot, grant rewards.

        The terminal transition, the dweller restore and the reward settlement commit
        exactly once. A failure rolls all three back, so the run stays RETURNING and the
        next tick retries it instead of leaving an arrived run with no rewards.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            dict: Rewards summary
        """
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)

        if not exploration.is_returning():
            raise ValueError(ERROR_NOT_RETURNING)
        if exploration.return_time_remaining_seconds() > 0:
            raise ValueError(ERROR_NOT_ARRIVED)

        recalled_early = exploration.recalled_early
        progress = exploration.exploring_progress_percentage()

        try:
            await crud_exploration.finalize_return(db_session, exploration_id=exploration_id)
            await self._update_dweller_status_after_return(db_session, exploration)
            if recalled_early:
                rewards = await rewards_service.apply_rewards(db_session, exploration, progress / 100, commit=False)
                rewards = rewards.model_copy(update={"progress_percentage": progress, "recalled_early": True})
            else:
                rewards = await rewards_service.apply_rewards(db_session, exploration, commit=False)
            await db_session.commit()
        except Exception:
            notification_service.discard_deferred_notifications(db_session)
            leveling_service.discard_deferred_level_ups(db_session)
            rewards_service.discard_pending_rewards(db_session)
            await db_session.rollback()
            raise

        await notification_service.deliver_deferred_notifications(db_session)
        await leveling_service.deliver_deferred_level_ups(db_session)
        await rewards_service.deliver_pending_reward_events(db_session)
        await self._notify_arrival(db_session, exploration, rewards)
        await event_service.publish_sse(
            exploration,
            "exploration_recalled" if recalled_early else "exploration_complete",
            rewards=rewards.model_dump(mode="json"),
        )

        return rewards

    async def _notify_arrival(self, db_session: AsyncSession, exploration: Exploration, rewards: RewardsSchema) -> None:
        """Send the arrival notification; best-effort, never breaks finalization."""
        try:
            dweller = await dweller_crud.get(db_session, exploration.dweller_id)
            vault = await crud_vault.get(db_session, exploration.vault_id)

            if vault and vault.user_id and dweller:
                dweller_name = f"{dweller.first_name} {dweller.last_name or ''}".strip()
                await notification_service.notify_exploration_complete(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=exploration.vault_id,
                    dweller_id=dweller.id,
                    dweller_name=dweller_name,
                    meta_data={
                        "exploration_id": str(exploration.id),
                        "caps_earned": rewards.caps,
                        "xp_earned": rewards.experience,
                        "items_found": len(rewards.items),
                        "dweller_id": str(dweller.id),
                        "dweller_name": dweller_name,
                        "rewards": rewards.model_dump(mode="json"),
                    },
                )
        except Exception:
            logger.exception(
                "Failed to send exploration complete notification: vault_id=%s, dweller_id=%s",
                exploration.vault_id,
                exploration.dweller_id,
            )

    async def _update_dweller_status_after_return(self, db_session: AsyncSession, exploration: Exploration) -> None:
        """Restore the dweller's room-appropriate status after exploration."""
        from app.core.enums import DwellerStatusEnum
        from app.crud.dweller import determine_status_for_room
        from app.schemas.dweller import DwellerUpdate

        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)

        if dweller_obj.room_id:
            # Dweller has a room - set status based on room type
            from app.crud.room import room as room_crud

            room_obj = await room_crud.get(db_session, dweller_obj.room_id)
            new_status = determine_status_for_room(room_obj.category, room_obj.name)
        else:
            # No room - set to IDLE
            new_status = DwellerStatusEnum.IDLE

        await dweller_crud.update(db_session, exploration.dweller_id, DwellerUpdate(status=new_status), commit=False)


# Singleton instance
exploration_coordinator = ExplorationCoordinator()
