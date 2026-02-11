"""Event handlers for objective-related events.

Listens to OBJECTIVE_COMPLETED and creates notifications.
"""

import logging
from typing import Any

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import async_session_maker
from app.models.objective import Objective
from app.models.vault import Vault
from app.services.event_bus import GameEvent, event_bus
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


async def _get_vault_owner(db_session: AsyncSession, vault_id: UUID4) -> UUID4 | None:
    """Get the owner user_id for a vault."""
    result = await db_session.execute(select(Vault).where(Vault.id == vault_id))
    vault = result.scalar_one_or_none()
    return vault.user_id if vault else None


async def _get_objective(db_session: AsyncSession, objective_id: UUID4) -> Objective | None:
    """Get objective by ID."""
    result = await db_session.execute(select(Objective).where(Objective.id == objective_id))
    return result.scalar_one_or_none()


async def handle_objective_completed(_event_type: str, vault_id: UUID4, data: dict[str, Any]) -> None:
    """Handle OBJECTIVE_COMPLETED event - send notification to vault owner."""
    objective_id = data.get("objective_id")
    challenge = data.get("challenge", "Unknown objective")

    if not objective_id:
        logger.warning("OBJECTIVE_COMPLETED event missing objective_id")
        return

    async with async_session_maker() as db_session:
        try:
            # Get objective to fetch reward
            objective = await _get_objective(db_session, UUID4(objective_id))
            if not objective:
                logger.warning(f"Objective {objective_id} not found")
                return

            # Get vault owner
            user_id = await _get_vault_owner(db_session, vault_id)
            if not user_id:
                logger.warning(f"Vault {vault_id} has no owner, skipping notification")
                return

            # Send notification
            await notification_service.notify_objective_completed(
                db=db_session,
                user_id=user_id,
                vault_id=vault_id,
                objective_challenge=challenge,
                reward=objective.reward,
                meta_data={"objective_id": str(objective_id), "reward": objective.reward},
            )

            logger.info(f"Objective completion notification sent for '{challenge}' to user {user_id}")

        except Exception:
            logger.exception(f"Failed to send objective completion notification for {objective_id}")


def register_objective_event_handlers() -> None:
    """Register event handlers for objective events."""
    event_bus.subscribe(GameEvent.OBJECTIVE_COMPLETED, handle_objective_completed)
    logger.info("Registered handler for OBJECTIVE_COMPLETED event")
