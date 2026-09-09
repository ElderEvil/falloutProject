"""WebSocket endpoints for real-time communication."""

import json
import logging
from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, WebSocket
from jose import JWTError, jwt
from pydantic import UUID4

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

    from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.crud.user import user as user_crud
from app.db.session import async_session_maker
from app.services.chat_service import chat_service
from app.services.websocket_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


def _decode_ws_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


async def _handle_chat_message(websocket: WebSocket, data: str, user_id: UUID4, dweller_id: UUID4) -> None:
    """Parse and dispatch a single chat WebSocket message."""
    try:
        message = json.loads(data)
        if not isinstance(message, dict):
            await websocket.send_json({"type": "error", "message": "Message must be a JSON object"})
            return

        message_type = message.get("type")

        if message_type == "ping":
            await websocket.send_json({"type": "pong"})

        elif message_type == "typing":
            is_typing = message.get("is_typing", False)
            await manager.send_typing_indicator(
                user_id=user_id, dweller_id=dweller_id, is_typing=is_typing, sender="user"
            )

        elif message_type == "message":
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                await websocket.send_json({"type": "error", "detail": "Message content must be a non-empty string"})
                return

            session_context = cast("AbstractAsyncContextManager[AsyncSession]", async_session_maker())
            async with session_context as db_session:
                user = await user_crud.get(db_session, user_id)
                if not user:
                    await websocket.send_json({"type": "error", "detail": "User not found"})
                    return

                async for chunk in chat_service.stream_response(
                    db_session=db_session,
                    user=user,
                    dweller_id=dweller_id,
                    message_text=content,
                ):
                    await websocket.send_json(chunk.model_dump(mode="json", exclude_none=True))

        else:
            await websocket.send_json({"type": "error", "message": f"Unknown message type: {message_type}"})

    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid JSON format"})


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: UUID4):
    """Handle a notification WebSocket connection."""
    await manager.connect(websocket, user_id)
    # Keep connection alive and handle incoming messages if needed
    async for data in websocket.iter_text():
        # Echo back for testing
        if data == "ping":
            await websocket.send_json({"type": "pong"})

    manager.disconnect(websocket, user_id)


@router.websocket("/ws/chat/{user_id}/{dweller_id}")
async def chat_websocket_endpoint(websocket: WebSocket, user_id: UUID4, dweller_id: UUID4):
    """Handle an authenticated dweller-chat WebSocket connection."""
    # WS Auth: verify token matches user_id BEFORE accepting/registering the connection.
    # Closing before accept() causes Starlette to reject the WebSocket handshake (HTTP 403),
    # so an unauthenticated socket is never registered with the connection manager.
    token = websocket.query_params.get("token")
    authenticated_user_id = _decode_ws_token(token) if token else None

    if not authenticated_user_id or authenticated_user_id != str(user_id):
        await websocket.close(code=4008)
        return

    await manager.connect_chat(websocket, user_id, dweller_id)
    logger.info("Chat WebSocket connected: user=%s, dweller=%s", user_id, dweller_id)

    try:
        async for data in websocket.iter_text():
            await _handle_chat_message(websocket, data, user_id, dweller_id)
    finally:
        logger.info("Chat WebSocket disconnected: user=%s, dweller=%s", user_id, dweller_id)
        manager.disconnect_chat(websocket, user_id, dweller_id)
