import asyncio
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time notifications and chat"""

    def __init__(self):
        # Map of user_id -> list of WebSocket connections (for notifications)
        self.active_connections: dict[UUID, list[WebSocket]] = {}
        # Map of (user_id, dweller_id) -> list of WebSocket connections (for chat)
        self.chat_connections: dict[tuple[UUID, UUID], list[WebSocket]] = {}

        # Redis integration for distributed broadcasting
        self.redis: Redis | None = None
        self.instance_id = str(uuid4())
        self.listener_task: asyncio.Task | None = None
        self.redis_channel = "ws_broadcast"

    async def start_redis(self):
        """Initialize Redis connection and start listener task"""
        if self.redis:
            return

        try:
            self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
            # Test connection
            await self.redis.ping()

            # Start background listener
            self.listener_task = asyncio.create_task(self._redis_listener())
            logger.info("Distributed WebSocket manager started (ID: %s)", self.instance_id)
        except Exception:
            logger.exception("Failed to initialize Redis for WebSocket manager. Running in local-only mode.")
            self.redis = None

    async def stop_redis(self):
        """Close Redis connection and cancel listener"""
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass

        if self.redis:
            await self.redis.close()
            self.redis = None

    async def _redis_listener(self):
        """Background task to listen for broadcast messages from other instances/workers"""
        if not self.redis:
            return

        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.redis_channel)

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])

                    # Ignore messages from self
                    if data.get("sender_instance") == self.instance_id:
                        continue

                    msg_type = data.get("msg_type")
                    payload = data.get("payload")

                    if msg_type == "personal":
                        user_id = UUID(data.get("user_id"))
                        await self._send_personal_local(payload, user_id)
                    elif msg_type == "chat":
                        user_id = UUID(data.get("user_id"))
                        dweller_id = UUID(data.get("dweller_id"))
                        await self._send_chat_local(payload, user_id, dweller_id)

                except Exception:
                    logger.exception("Error processing broadcast message from Redis")
        finally:
            await pubsub.unsubscribe(self.redis_channel)
            await pubsub.close()

    async def _publish(self, data: dict[str, Any]):
        """Publish a message to Redis for other instances to pick up"""
        if not self.redis:
            # If not yet initialized, attempt lazy init (safe for workers)
            await self.start_redis()

        if self.redis:
            data["sender_instance"] = self.instance_id
            try:
                await self.redis.publish(self.redis_channel, json.dumps(data))
            except Exception:  # noqa: BLE001
                logger.error("Failed to publish WebSocket message to Redis")

    async def connect(self, websocket: WebSocket, user_id: UUID):
        """Connect a new WebSocket for a user"""
        await websocket.accept()

        # Ensure Redis listener is running in web process
        await self.start_redis()

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
        """Send a message to all connections for a specific user (distributed)"""
        # 1. Send locally
        await self._send_personal_local(message, user_id)

        # 2. Broadcast to other instances via Redis
        await self._publish({"msg_type": "personal", "user_id": str(user_id), "payload": message})

    async def _send_personal_local(self, message: dict[str, Any], user_id: UUID):
        """Send message only to locally connected sockets"""
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

        # Ensure Redis listener is running
        await self.start_redis()

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
        """Send a message to all connections for a specific chat session (distributed)"""
        # 1. Send locally
        await self._send_chat_local(message, user_id, dweller_id)

        # 2. Broadcast to other instances
        await self._publish(
            {"msg_type": "chat", "user_id": str(user_id), "dweller_id": str(dweller_id), "payload": message}
        )

    async def _send_chat_local(self, message: dict[str, Any], user_id: UUID, dweller_id: UUID):
        """Send message only to locally connected sockets"""
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
