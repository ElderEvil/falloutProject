from typing import Any
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections for real-time notifications and chat"""

    def __init__(self):
        # Map of user_id -> list of WebSocket connections (for notifications)
        self.active_connections: dict[UUID, list[WebSocket]] = {}
        # Map of (user_id, dweller_id) -> list of WebSocket connections (for chat)
        self.chat_connections: dict[tuple[UUID, UUID], list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: UUID):
        """Connect a new WebSocket for a user"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: UUID):
        """Disconnect a WebSocket for a user"""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            # Clean up empty lists
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: dict[str, Any], user_id: UUID):
        """Send a message to all connections for a specific user"""
        if user_id in self.active_connections:
            # Send to all active connections for this user
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except (RuntimeError, ConnectionError):
                    # Mark for removal if connection is broken
                    disconnected.append(connection)

            # Clean up broken connections
            for connection in disconnected:
                self.disconnect(connection, user_id)

    async def broadcast_to_vault(self, message: dict[str, Any], vault_id: UUID, user_ids: list[UUID]):  # noqa: ARG002
        """Broadcast a message to all users in a vault"""
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    async def connect_chat(self, websocket: WebSocket, user_id: UUID, dweller_id: UUID):
        """Connect a new WebSocket for a specific chat session"""
        await websocket.accept()
        chat_key = (user_id, dweller_id)
        if chat_key not in self.chat_connections:
            self.chat_connections[chat_key] = []
        self.chat_connections[chat_key].append(websocket)

    def disconnect_chat(self, websocket: WebSocket, user_id: UUID, dweller_id: UUID):
        """Disconnect a WebSocket for a specific chat session"""
        chat_key = (user_id, dweller_id)
        if chat_key in self.chat_connections:
            if websocket in self.chat_connections[chat_key]:
                self.chat_connections[chat_key].remove(websocket)
            # Clean up empty lists
            if not self.chat_connections[chat_key]:
                del self.chat_connections[chat_key]

    async def send_chat_message(self, message: dict[str, Any], user_id: UUID, dweller_id: UUID):
        """Send a message to all connections for a specific chat session"""
        chat_key = (user_id, dweller_id)
        if chat_key in self.chat_connections:
            disconnected = []
            for connection in self.chat_connections[chat_key]:
                try:
                    await connection.send_json(message)
                except (RuntimeError, ConnectionError):
                    disconnected.append(connection)

            # Clean up broken connections
            for connection in disconnected:
                self.disconnect_chat(connection, user_id, dweller_id)

    async def send_typing_indicator(self, user_id: UUID, dweller_id: UUID, *, is_typing: bool, sender: str = "dweller"):
        """Send typing indicator to chat participants"""
        await self.send_chat_message(
            {"type": "typing", "is_typing": is_typing, "sender": sender},
            user_id,
            dweller_id,
        )


# Global connection manager instance
manager = ConnectionManager()
