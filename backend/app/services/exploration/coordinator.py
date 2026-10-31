"""Exploration coordinator - orchestrates exploration completion and recall."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import dweller as dweller_crud
from app.crud import exploration as crud_exploration
from app.models.exploration import Exploration
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration.event_service import event_service
from app.services.exploration.journey_state import (
    close_open_site_run,
    delete_journey_team,
    restore_journey_dwellers,
)
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
        self, db_session: AsyncSession, exploration_id: UUID4, *, recalled: bool = False, arrived: bool = False
    ) -> Exploration:
        """Send a dweller home; rewards and loot wait until the return leg finishes.

        Args:
            db_session: Database session
            exploration_id: Exploration ID
            recalled: True for a player-initiated early recall, False for a natural finish
            arrived: True when a spatial dispatch reached its target; arrival finishes
                the outbound leg regardless of remaining planned time

        Returns:
            Exploration: The exploration now in RETURNING state
        """
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError(ERROR_NOT_ACTIVE)
        if not recalled and not arrived and exploration.time_remaining_seconds() > 0:
            raise ValueError("Exploration has not finished yet; recall the dweller to end it early")

        # Clock expiry and recall both force-retreat an open site run before the
        # return leg starts, all in this one transaction.
        await close_open_site_run(db_session, exploration_id)

        from app.services.exploration_service import exploration_service

        exploration_service.resume_from_encounter(exploration)
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
            await restore_journey_dwellers(db_session, exploration)
            if recalled_early:
                rewards = await rewards_service.apply_rewards(db_session, exploration, progress / 100, commit=False)
                rewards = rewards.model_copy(update={"progress_percentage": progress, "recalled_early": True})
            else:
                rewards = await rewards_service.apply_rewards(db_session, exploration, commit=False)
            await delete_journey_team(db_session, exploration)
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

        async def send(user_id: UUID4) -> None:
            dweller = await dweller_crud.get(db_session, exploration.dweller_id)
            dweller_name = f"{dweller.first_name} {dweller.last_name or ''}".strip()
            await notification_service.notify_exploration_complete(
                db_session,
                user_id=user_id,
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

        await notification_service.notify_owner(
            db_session,
            exploration.vault_id,
            sender=send,
            context=f"exploration complete vault={exploration.vault_id} dweller={exploration.dweller_id}",
        )


# Singleton instance
exploration_coordinator = ExplorationCoordinator()
