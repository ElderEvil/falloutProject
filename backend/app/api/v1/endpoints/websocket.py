import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import UUID4

from app.services.websocket_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/{user_id}")
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
    try:
        # Keep connection alive and handle incoming messages if needed
        while True:
            # Wait for any messages from client (ping/pong, etc.)
            data = await websocket.receive_text()

            # Echo back for testing
            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


@router.websocket("/ws/chat/{user_id}/{dweller_id}")
async def chat_websocket_endpoint(websocket: WebSocket, user_id: UUID4, dweller_id: UUID4):
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

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                message_type = message.get("type")

                if message_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif message_type == "typing":
                    # Broadcast typing indicator
                    is_typing = message.get("is_typing", False)
                    await manager.send_typing_indicator(
                        user_id=user_id, dweller_id=dweller_id, is_typing=is_typing, sender="user"
                    )

                elif message_type == "message":
                    # For now, just acknowledge receipt
                    # Full text chat via WebSocket can be implemented later
                    # Currently, text chat uses REST API /api/v1/chat/{dweller_id}
                    await websocket.send_json(
                        {"type": "ack", "message": "Message received. Use REST API for full chat functionality."}
                    )

                else:
                    await websocket.send_json({"type": "error", "message": f"Unknown message type: {message_type}"})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON format"})

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected: user=%s, dweller=%s", user_id, dweller_id)
        manager.disconnect_chat(websocket, user_id, dweller_id)
