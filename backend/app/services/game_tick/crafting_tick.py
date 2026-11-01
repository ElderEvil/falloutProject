"""Game tick phase for the workshop crafting queue."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.game_config import game_config
from app.services.crafting_service import crafting_service
from app.services.game_tick.tick_results import CraftingStats

logger = logging.getLogger(__name__)


def crafting_advance_due(*, total_game_time: int, seconds_passed: int) -> bool:
    """Whether this tick crosses a crafting-check boundary in authoritative game time.

    The cadence is anchored to ``GameState.total_game_time``, so every worker
    agrees and a catch-up tick that spans one or more boundaries still checks the
    queue. Previous time is floored at zero: a tick whose resource phase failed
    did not advance game time, and must not look like it crossed a boundary.
    """
    cadence = settings.CRAFTING_ADVANCE_EVERY_N_TICKS * game_config.game_loop.tick_interval
    previous_game_time = max(0, total_game_time - seconds_passed)
    return total_game_time // cadence != previous_game_time // cadence


async def process_crafting(
    db_session: AsyncSession,
    vault_id: UUID4,
    *,
    total_game_time: int,
    seconds_passed: int,
) -> CraftingStats:
    """Check a vault's wall-clock crafting queue when this tick crosses the cadence."""
    if not crafting_advance_due(total_game_time=total_game_time, seconds_passed=seconds_passed):
        return {"completed": 0}
    completed = await crafting_service.advance_orders(db_session, vault_id)
    if completed:
        # Local import avoids a circular import, matching the other tick phases.
        from app.services.notification_service import notification_service

        await notification_service.notify_owner(
            db_session,
            vault_id,
            context=f"crafting_complete vault={vault_id} orders={completed}",
            sender=lambda user_id: notification_service.notify_crafting_complete(
                db_session, user_id=user_id, vault_id=vault_id, order_count=completed
            ),
        )
        logger.info(f"Crafting orders completed for vault {vault_id}: {completed}")
    return {"completed": completed}
