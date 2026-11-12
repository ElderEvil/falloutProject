"""WebSocket connection manager for real-time notifications and chat."""

import asyncio
import contextlib
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.stream_manager import sse_manager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with Redis pub/sub for distributed setup.

    Supports both personal notifications and chat sessions with automatic
    reconnection handling and cross-instance message broadcasting.
    """

    def __init__(self):
        self.active_connections: dict[UUID, list[WebSocket]] = {}
        self.chat_connections: dict[tuple[UUID, UUID], list[WebSocket]] = {}
        self.redis: Redis | None = None
        # Ephemeral process identifier; not a persisted row.
        self.instance_id = str(uuid4())
        self.listener_task: asyncio.Task | None = None
        self._redis_ready: asyncio.Event | None = None
        self._redis_retry_delay = 1
        self.redis_channel = "ws_broadcast"

    async def start_redis(self):
        """Initialize Redis connection and start listener task."""
        if self.redis is None:
            self.redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=5)
            self._redis_ready = asyncio.Event()
            self.listener_task = asyncio.create_task(self._redis_listener())
            logger.info("Redis notification listener task created (ID: %s)", self.instance_id)
        ready = self._redis_ready
        if ready is not None:
            try:
                await asyncio.wait_for(ready.wait(), timeout=5)
            except TimeoutError:
                # A late subscription must also close streams which connected
                # after startup timed out, so they reload notifications missed here.
                ready.set()
                logger.warning("Redis subscription is not ready; listener will continue connecting")

    async def stop_redis(self):
        """Close Redis connection and cancel listener."""
        listener, self.listener_task = self.listener_task, None
        client, self.redis = self.redis, None
        if self._redis_ready:
            self._redis_ready.set()
        self._redis_ready = None
        try:
            if listener:
                listener.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await listener
        finally:
            if client:
                await client.aclose()

    async def _process_redis_message(self, message: dict):
        """Process a single Redis message."""
        if message["type"] != "message":
            return

        data = json.loads(message["data"])
        if not isinstance(data, dict):
            raise TypeError("Redis broadcast must be an object")
        if data.get("sender_instance") == self.instance_id:
            return

        msg_type = data.get("msg_type")
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise TypeError("Redis broadcast payload must be an object")

        if msg_type == "personal":
            user_id = UUID(data["user_id"])
            await self._send_personal_local(payload, user_id)
            if payload.get("type") == "notification":
                await sse_manager.publish(user_id, "notifications", payload)
        elif msg_type == "chat":
            user_id = UUID(data["user_id"])
            dweller_id = UUID(data["dweller_id"])
            await self._send_chat_local(payload, user_id, dweller_id)

    async def _handle_redis_message(self, message: dict) -> None:
        try:
            await self._process_redis_message(message)
        except KeyError, ValueError, TypeError:
            logger.exception("Invalid Redis broadcast")

    async def _consume_redis(self, client: Redis, ready: asyncio.Event) -> None:
        async with client.pubsub() as pubsub:
            await pubsub.subscribe(self.redis_channel)
            try:
                async for message in pubsub.listen():
                    if message["type"] == "subscribe":
                        # redis-py can reconnect/resubscribe internally. Force SSE clients
                        # to catch up from persisted notifications after any gap.
                        if ready.is_set():
                            await sse_manager.close(topic="notifications")
                        self._redis_retry_delay = 1
                        ready.set()
                    else:
                        await self._handle_redis_message(message)
            finally:
                # A disconnected socket is already unsubscribed on the server.
                with contextlib.suppress(RedisError, OSError):
                    await pubsub.unsubscribe(self.redis_channel)

    async def _redis_listener(self) -> None:
        """Reconnect the API's Redis subscriber and invalidate streams across gaps."""
        client, ready = self.redis, self._redis_ready
        if client is None or ready is None:
            return
        self._redis_retry_delay = 1
        try:
            while True:
                try:
                    await self._consume_redis(client, ready)
                except (RedisError, OSError) as error:
                    logger.warning(
                        "Redis notification listener unavailable; retrying in %ss: %s", self._redis_retry_delay, error
                    )
                ready.set()
                # Keep local SSE alive during outages; resubscription triggers catch-up once.
                await asyncio.sleep(self._redis_retry_delay)
                self._redis_retry_delay = min(self._redis_retry_delay * 2, 30)
        finally:
            ready.set()

    async def _publish(self, data: dict[str, Any]):
        """Publish message to Redis for other instances."""
        data["sender_instance"] = self.instance_id
        encoded = json.dumps(jsonable_encoder(data))
        try:
            if self.redis is not None:
                await self.redis.publish(self.redis_channel, encoded)
            else:
                # Worker threads use different event loops. A publisher-only client
                # belongs to this call, rather than a process-global listener loop.
                async with Redis.from_url(settings.redis_url, decode_responses=True) as publisher:
                    await publisher.publish(self.redis_channel, encoded)
        except RedisError, RedisConnectionError:
            logger.exception("Failed to publish WS message to Redis")
        except RuntimeError, AttributeError:
            # Event loop closed during tests or shutdown - suppress
            logger.debug("Redis publish skipped (event loop closed)")

    async def connect(self, websocket: WebSocket, user_id: UUID):
        """Connect WebSocket for user notifications.

        :param websocket: WebSocket connection
        :type websocket: WebSocket
        :param user_id: User ID
        :type user_id: UUID
        """
        await websocket.accept()
        await self.start_redis()

        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: UUID):
        """Disconnect WebSocket for user notifications.

        :param websocket: WebSocket connection
        :type websocket: WebSocket
        :param user_id: User ID
        :type user_id: UUID
        """
        if user_id not in self.active_connections:
            return

        with contextlib.suppress(ValueError):
            self.active_connections[user_id].remove(websocket)

        if not self.active_connections[user_id]:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict[str, Any], user_id: UUID):
        """Send message to all user connections across instances.

        :param message: Message payload
        :type message: dict[str, Any]
        :param user_id: Target user ID
        :type user_id: UUID
        """
        await self._send_personal_local(message, user_id)
        await self._publish(
            {
                "msg_type": "personal",
                "user_id": str(user_id),
                "payload": message,
            }
        )

    async def _send_personal_local(self, message: dict[str, Any], user_id: UUID):
        """Send message to locally connected sockets only."""
        connections = self.active_connections.get(user_id, [])
        disconnected = []

        for conn in connections:
            try:
                await conn.send_json(message)
            except (RuntimeError, ConnectionError) as e:
                logger.debug("Connection closed for user %s: %s", user_id, e)
                disconnected.append(conn)

        for conn in disconnected:
            self.disconnect(conn, user_id)

    async def broadcast_to_vault(
        self,
        message: dict[str, Any],
        vault_id: UUID,
        user_ids: list[UUID],
    ):
        """Broadcast message to all users in a vault.

        :param message: Message payload
        :type message: dict[str, Any]
        :param vault_id: Vault ID (unused, kept for API compatibility)
        :type vault_id: UUID
        :param user_ids: List of user IDs to broadcast to
        :type user_ids: list[UUID]
        """
        await asyncio.gather(*[self.send_personal_message(message, uid) for uid in user_ids])

    async def connect_chat(self, websocket: WebSocket, user_id: UUID, dweller_id: UUID):
        """Connect WebSocket for chat session.

        :param websocket: WebSocket connection
        :type websocket: WebSocket
        :param user_id: User ID
        :type user_id: UUID
        :param dweller_id: Dweller ID
        :type dweller_id: UUID
        """
        await websocket.accept()
        await self.start_redis()

        chat_key = (user_id, dweller_id)
        self.chat_connections.setdefault(chat_key, []).append(websocket)

    def disconnect_chat(self, websocket: WebSocket, user_id: UUID, dweller_id: UUID):
        """Disconnect WebSocket for chat session.

        :param websocket: WebSocket connection
        :type websocket: WebSocket
        :param user_id: User ID
        :type user_id: UUID
        :param dweller_id: Dweller ID
        :type dweller_id: UUID
        """
        chat_key = (user_id, dweller_id)
        if chat_key not in self.chat_connections:
            return

        with contextlib.suppress(ValueError):
            self.chat_connections[chat_key].remove(websocket)

        if not self.chat_connections[chat_key]:
            del self.chat_connections[chat_key]

    async def send_chat_message(self, message: dict[str, Any], user_id: UUID, dweller_id: UUID):
        """Send message to all chat session connections across instances.

        :param message: Message payload
        :type message: dict[str, Any]
        :param user_id: User ID
        :type user_id: UUID
        :param dweller_id: Dweller ID
        :type dweller_id: UUID
        """
        await self._send_chat_local(message, user_id, dweller_id)
        await self._publish(
            {
                "msg_type": "chat",
                "user_id": str(user_id),
                "dweller_id": str(dweller_id),
                "payload": message,
            }
        )

    async def _send_chat_local(self, message: dict[str, Any], user_id: UUID, dweller_id: UUID):
        """Send message to locally connected chat sockets only."""
        chat_key = (user_id, dweller_id)
        connections = self.chat_connections.get(chat_key, [])
        disconnected = []

        for conn in connections:
            try:
                await conn.send_json(message)
            except (RuntimeError, ConnectionError) as e:
                logger.debug(
                    "Connection closed for chat %s-%s: %s",
                    user_id,
                    dweller_id,
                    e,
                )
                disconnected.append(conn)

        for conn in disconnected:
            self.disconnect_chat(conn, user_id, dweller_id)

    async def send_typing_indicator(
        self,
        user_id: UUID,
        dweller_id: UUID,
        *,
        is_typing: bool,
        sender: str = "dweller",
    ):
        """Send typing indicator to chat participants.

        :param user_id: User ID
        :type user_id: UUID
        :param dweller_id: Dweller ID
        :type dweller_id: UUID
        :param is_typing: Whether typing is active
        :type is_typing: bool
        :param sender: Who is typing, defaults to "dweller"
        :type sender: str
        """
        await self.send_chat_message(
            {"type": "typing", "is_typing": is_typing, "sender": sender},
            user_id,
            dweller_id,
        )


manager = ConnectionManager()
