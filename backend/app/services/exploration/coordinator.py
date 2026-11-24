"""Exploration coordinator - orchestrates exploration completion and recall."""

import logging
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ExplorationPurpose
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
from app.utils.exceptions import ValidationException
from app.utils.serialize import serialize_optional_utc_datetime

logger = logging.getLogger(__name__)

# Error messages as constants to satisfy ruff
ERROR_NOT_ACTIVE = "Exploration is not active"
ERROR_NOT_RETURNING = "Exploration is not on the return leg"
ERROR_NOT_ARRIVED = "Exploration has not arrived home yet"


def _contribution_weight(run: Exploration) -> int:
    """World-event units one resolved run is worth.

    A trade caravan contributes nothing (issue 1493): it is the safe faucet, and letting it feed world
    events would make the cheap trip the optimal way to move a shared goal. Otherwise ``clear_tier`` is
    the difficulty signal — NULL on a free-roam trip, the escalation tier on a dispatch sent to clear.
    """
    if run.purpose == ExplorationPurpose.TRADE:
        return 0
    return 3 if run.clear_tier is not None else 1


class ExplorationCoordinator:
    """Coordinates exploration completion and recall; events and rewards live in their own services."""

    async def start_return(
        self, db_session: AsyncSession, exploration_id: UUID, *, recalled: bool = False, arrived: bool = False
    ) -> Exploration:
        """Send a dweller home; rewards and loot wait until the return leg finishes."""
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)

        if not exploration.is_active():
            raise ValidationException(detail=ERROR_NOT_ACTIVE)
        if not recalled and not arrived and exploration.time_remaining_seconds() > 0:
            raise ValidationException(detail="Exploration has not finished yet; recall the dweller to end it early")

        # Clock expiry and recall both force-retreat an open site run before the return leg starts, all in this one
        # transaction.
        await close_open_site_run(db_session, exploration_id)

        from app.services.exploration_service import exploration_service

        exploration_service.resume_from_encounter(exploration)
        exploration = await crud_exploration.start_return(db_session, exploration_id=exploration_id, recalled=recalled)
        await db_session.commit()

        await event_service.publish_sse(
            exploration,
            "exploration_returning",
            recalled=recalled,
            return_started_at=serialize_optional_utc_datetime(exploration.return_started_at),
            return_completes_at=serialize_optional_utc_datetime(exploration.return_completes_at),
        )

        return exploration

    async def finalize_return(self, db_session: AsyncSession, exploration_id: UUID) -> RewardsSchema:
        """Finalize an arrived exploration: restore the dweller, release loot, grant rewards.

        Terminal transition, dweller restore, and reward settlement commit exactly once; failure rolls all three
        back so the run stays RETURNING and the next tick retries.
        """
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)

        if not exploration.is_returning():
            raise ValidationException(detail=ERROR_NOT_RETURNING)
        if exploration.return_time_remaining_seconds() > 0:
            raise ValidationException(detail=ERROR_NOT_ARRIVED)

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

        # Post-commit: the run is already terminal, so a retry cannot double-credit. A failure here must
        # not undo a finalised run, hence its own commit/rollback.
        from app.services.world_event_service import world_event_service

        try:
            await world_event_service.record_contribution(
                db_session, exploration.vault_id, _contribution_weight(exploration), kind="expedition"
            )
            await db_session.commit()
        except Exception:
            logger.exception("world event contribution (expedition) failed")
            await db_session.rollback()

        await self._notify_arrival(db_session, exploration, rewards)
        await event_service.publish_sse(
            exploration,
            "exploration_recalled" if recalled_early else "exploration_complete",
            rewards=rewards.model_dump(mode="json"),
        )

        return rewards

    async def _notify_arrival(self, db_session: AsyncSession, exploration: Exploration, rewards: RewardsSchema) -> None:
        """Send the arrival notification; best-effort, never breaks finalization."""

        async def send(user_id: UUID) -> None:
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
