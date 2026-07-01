import json
import logging

from fastapi import APIRouter, WebSocket
from pydantic import UUID4

from app import crud
from app.db.session import async_session_maker
from app.services.chat_service import chat_service
from app.services.websocket_manager import manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])
logger = logging.getLogger(__name__)


@router.websocket("/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: UUID4):
    """
    WebSocket endpoint for real-time notifications.

    Connect to this endpoint to receive real-time notifications:
    ws://localhost:8000/api/v1/ws/{user_id}

    Messages format:
    {
        "type": "notification",
        "notification": {
            "id": "uuid",
            "notification_type": "exploration_update",
            "priority": "normal",
            "title": "Title",
            "message": "Message",
            "meta_data": {...},
            "created_at": "ISO timestamp"
        }
    }
    """
    await manager.connect(websocket, user_id)
    # Keep connection alive and handle incoming messages if needed
    async for data in websocket.iter_text():
        # Echo back for testing
        if data == "ping":
            await websocket.send_json({"type": "pong"})

    manager.disconnect(websocket, user_id)


@router.websocket("/chat/{user_id}/{dweller_id}")
async def chat_websocket_endpoint(websocket: WebSocket, user_id: UUID4, dweller_id: UUID4):  # noqa: C901,PLR0912
    """
    WebSocket endpoint for real-time chat with a dweller.

    Connect to this endpoint for real-time text chat:
    ws://localhost:8000/api/v1/ws/chat/{user_id}/{dweller_id}

    Client -> Server messages:
    {
        "type": "message",
        "content": "Hello dweller!"
    }
    {
        "type": "typing",
        "is_typing": true
    }

    Server -> Client messages:
    {
        "type": "message",
        "content": "Hello overseer!",
        "sender": "dweller"
    }
    {
        "type": "typing",
        "is_typing": true,
        "sender": "dweller"
    }
    {
        "type": "error",
        "message": "Error description"
    }
    """
    await manager.connect_chat(websocket, user_id, dweller_id)
    logger.info("Chat WebSocket connected: user=%s, dweller=%s", user_id, dweller_id)

    async for data in websocket.iter_text():
        # Handle VueUse's raw heartbeat 'ping' (not JSON)
        if data == "ping":
            await websocket.send_json({"type": "pong"})
            continue

        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "message": "Invalid JSON format"})
            continue

        message_type = message.get("type")

        if message_type == "ping":
            await websocket.send_json({"type": "pong"})

        elif message_type == "typing":
            is_typing = message.get("is_typing", False)
            await manager.send_typing_indicator(
                user_id=user_id, dweller_id=dweller_id, is_typing=is_typing, sender="user"
            )

        elif message_type == "message":
            content = message.get("content", "")
            if not content:
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            try:
                async with async_session_maker() as db_session:
                    user = await crud.user.get(db_session, user_id)
                    if not user:
                        await websocket.send_json({"type": "error", "message": "User not found"})
                        continue

                    async for chunk in chat_service.stream_response(
                        db_session=db_session,
                        user=user,
                        dweller_id=dweller_id,
                        message_text=content,
                    ):
                        chunk_type = chunk.get("type")
                        if chunk_type == "token":
                            await websocket.send_json({"type": "token", "content": chunk["text"]})
                        elif chunk_type == "done":
                            await websocket.send_json(
                                {
                                    "type": "done",
                                    "message_id": chunk["message_id"],
                                    "response": chunk["response"],
                                    "happiness_impact": chunk["happiness_impact"],
                                    "action_suggestion": chunk["action_suggestion"],
                                }
                            )
                        elif chunk_type == "error":
                            await websocket.send_json({"type": "error", "message": chunk["detail"]})
                            break
            except Exception:
                logger.exception("Chat streaming error")
                await websocket.send_json({"type": "error", "message": "An unexpected error occurred during chat"})

        else:
            await websocket.send_json({"type": "error", "message": f"Unknown message type: {message_type}"})

    logger.info("Chat WebSocket disconnected: user=%s, dweller=%s", user_id, dweller_id)
    manager.disconnect_chat(websocket, user_id, dweller_id)
