from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import UUID4

from app.services.websocket_manager import manager

router = APIRouter()


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
