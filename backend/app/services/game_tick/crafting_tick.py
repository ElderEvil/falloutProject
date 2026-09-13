"""Game tick phase for the workshop crafting queue."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.crafting_service import crafting_service
from app.services.game_tick.tick_results import CraftingStats

logger = logging.getLogger(__name__)


async def process_crafting(db_session: AsyncSession, vault_id: UUID4) -> CraftingStats:
    """Advance a vault's workshop queue, marking finished orders collectable."""
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
