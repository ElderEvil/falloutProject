"""Chat side-effects: WebSocket notifications and post-conversation place unlocks."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas.chat import ActionSuggestion, UnlockedPlace
from app.schemas.dweller import DwellerReadFull
from app.schemas.happiness import HappinessImpact
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)


async def send_chat_notification(
    user_id: UUID4,
    dweller_id: UUID4,
    dweller_message_id: UUID4,
    happiness_impact: HappinessImpact | None,
    action_suggestion: ActionSuggestion | None,
) -> None:
    """Send WebSocket notifications for happiness updates and action suggestions. Non-fatal."""
    try:
        if happiness_impact:
            await manager.send_chat_message(
                {
                    "type": "happiness_update",
                    "happiness_impact": happiness_impact.model_dump(mode="json"),
                    "message_id": str(dweller_message_id),
                },
                user_id=user_id,
                dweller_id=dweller_id,
            )

        if action_suggestion and action_suggestion.action_type != "no_action":
            await manager.send_chat_message(
                {
                    "type": "action_suggestion",
                    "action_suggestion": action_suggestion.model_dump(mode="json"),
                    "message_id": str(dweller_message_id),
                },
                user_id=user_id,
                dweller_id=dweller_id,
            )
    except Exception:
        logger.exception("Failed to send WebSocket notification, continuing with REST response")


async def maybe_unlock_places(db_session: AsyncSession, dweller: DwellerReadFull) -> list[UnlockedPlace]:
    """Unlock the dweller's associated places after 3+ user messages (best-effort)."""
    from app.crud.chat_message import chat_message as chat_crud
    from app.crud.world_location import world_location as wl_crud

    try:
        async with db_session.begin_nested():
            user_msg_count = await chat_crud.count_user_messages_to_dweller(db_session, dweller_id=dweller.id)
            if user_msg_count >= 3:
                unlocked_rows = await wl_crud.unlock_places_for_dweller(db_session, dweller_id=dweller.id)
                unlocked_places = [
                    UnlockedPlace(location_id=location_id, name=name) for location_id, name in unlocked_rows
                ]
                if unlocked_places:
                    logger.info(
                        "Unlocked %d places for dweller %s after %d user messages",
                        len(unlocked_places),
                        dweller.id,
                        user_msg_count,
                    )
                return unlocked_places
    except Exception:
        logger.exception("Failed to unlock places for dweller %s, continuing", dweller.id)
    return []


async def unlock_places_after_conversation(db_session: AsyncSession, dweller: DwellerReadFull) -> list[UnlockedPlace]:
    """Apply the shared post-message discovery rule for non-text chat flows."""
    return await maybe_unlock_places(db_session, dweller)
