"""Exploration coordinator - orchestrates exploration completion and recall."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import dweller as dweller_crud
from app.crud import exploration as crud_exploration
from app.crud import vault as crud_vault
from app.models.exploration import Exploration
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration.event_service import event_service
from app.services.exploration.rewards_service import rewards_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# Error messages as constants to satisfy ruff
ERROR_NOT_ACTIVE = "Exploration is not active"


class ExplorationCoordinator:
    """Coordinates exploration completion and recall; events and rewards live in their own services."""

    async def complete_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> RewardsSchema:
        """Complete an exploration and return rewards summary.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            dict: Rewards summary
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError(ERROR_NOT_ACTIVE)
        if exploration.time_remaining_seconds() > 0:
            raise ValueError("Exploration has not finished yet; recall the dweller to end it early")

        # Mark as completed
        await crud_exploration.complete_exploration(db_session, exploration_id=exploration_id)

        # Update dweller status
        await self._update_dweller_status_after_return(db_session, exploration)

        # Calculate and apply rewards
        rewards = await rewards_service.apply_rewards(db_session, exploration)

        # Send notification (non-critical, don't break completion on failure)
        try:
            dweller = await dweller_crud.get(db_session, exploration.dweller_id)
            vault = await crud_vault.get(db_session, exploration.vault_id)

            if vault and vault.user_id and dweller:
                await notification_service.notify_exploration_complete(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=exploration.vault_id,
                    dweller_id=dweller.id,
                    dweller_name=f"{dweller.first_name} {dweller.last_name or ''}".strip(),
                    meta_data={
                        "exploration_id": str(exploration.id),
                        "caps_earned": rewards.caps,
                        "xp_earned": rewards.experience,
                        "items_found": len(rewards.items),
                        "dweller_id": str(dweller.id),
                        "dweller_name": f"{dweller.first_name} {dweller.last_name or ''}".strip(),
                        "rewards": rewards.model_dump(mode="json"),
                    },
                )
        except Exception:
            logger.exception(
                "Failed to send exploration complete notification: vault_id=%s, dweller_id=%s",
                exploration.vault_id,
                exploration.dweller_id,
            )

        # Publish SSE event
        await event_service.publish_sse(
            exploration,
            "exploration_complete",
            rewards=rewards.model_dump(mode="json"),
        )

        return rewards

    async def recall_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> RewardsSchema:
        """Recall a dweller early from exploration.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            dict: Rewards summary with reduced XP
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError(ERROR_NOT_ACTIVE)

        # Calculate progress percentage
        progress = exploration.progress_percentage()

        # Mark as recalled
        await crud_exploration.recall_exploration(db_session, exploration_id=exploration_id)

        # Update dweller status
        await self._update_dweller_status_after_return(db_session, exploration)

        # Calculate and apply reduced rewards
        rewards = await rewards_service.apply_rewards(db_session, exploration, progress_multiplier=progress / 100)

        rewards = rewards.model_copy(update={"progress_percentage": progress, "recalled_early": True})

        await event_service.publish_sse(
            exploration,
            "exploration_recalled",
            rewards=rewards.model_dump(mode="json"),
        )

        return rewards

    async def _update_dweller_status_after_return(self, db_session: AsyncSession, exploration: Exploration) -> None:
        """Restore the dweller's room-appropriate status after exploration."""
        from app.crud.dweller import determine_status_for_room
        from app.schemas.common import DwellerStatusEnum
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

        await dweller_crud.update(db_session, exploration.dweller_id, DwellerUpdate(status=new_status))


# Singleton instance
exploration_coordinator = ExplorationCoordinator()
