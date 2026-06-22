"""SSE (Server-Sent Events) connection manager for real-time streaming.

Parallel to websocket_manager.py but for one-directional server→client SSE streams.
Uses asyncio.Queue per subscriber for fan-out.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages SSE subscriptions via in-memory pub/sub.

    Each (topic, user_id) pair can have multiple subscriber queues.
    Services publish events via publish(); SSE endpoint generators
    consume via subscribe().
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, dict[UUID, set[asyncio.Queue]]] = {}
        self._queue_maxsize = 256

    async def subscribe(
        self,
        user_id: UUID,
        topic: str,
        *,
        _after_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to events on a topic for a user.

        Yields dicts published to this topic+user. Cleans up the
        subscriber queue on exit (disconnect or CancelledError).

        Args:
            user_id: Target user UUID.
            topic: Event topic (e.g. "notifications", "game_ticks", "exploration").
            after_id: If set, reserved for future Last-Event-ID resume.

        Yields:
            Dicts with at least an ``event_id`` and ``data`` key.
        """
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._subscribers.setdefault(topic, {}).setdefault(user_id, set()).add(queue)

        logger.debug("SSE subscriber added: topic=%s user=%s", topic, user_id)

        try:
            while True:
                data = await queue.get()
                # None is a sentinel meaning "shutdown"
                if data is None:
                    break
                yield data
        except asyncio.CancelledError:
            logger.debug("SSE subscriber cancelled: topic=%s user=%s", topic, user_id)
            raise
        finally:
            self._unsubscribe(user_id, topic, queue)
            logger.debug("SSE subscriber removed: topic=%s user=%s", topic, user_id)

    def _unsubscribe(self, user_id: UUID, topic: str, queue: asyncio.Queue) -> None:
        """Remove a specific queue from the subscriber set."""
        topic_subs = self._subscribers.get(topic, {})
        user_queues = topic_subs.get(user_id, set())
        user_queues.discard(queue)
        if not user_queues:
            topic_subs.pop(user_id, None)
        if not topic_subs:
            self._subscribers.pop(topic, None)

    async def publish(
        self,
        user_id: UUID,
        topic: str,
        data: dict[str, Any],
    ) -> None:
        """Publish an event to all subscribers of (topic, user_id).

        Best-effort: drops events for queues that are full to avoid
        blocking the publisher.

        Args:
            user_id: Target user UUID.
            topic: Event topic.
            data: Event payload (should include ``event_id``).
        """
        user_queues = self._subscribers.get(topic, {}).get(user_id)
        if not user_queues:
            return

        dead: list[asyncio.Queue] = []
        for queue in user_queues:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning(
                    "SSE queue full for topic=%s user=%s — dropping event %s",
                    topic,
                    user_id,
                    data.get("event_id", "?"),
                )
            except (RuntimeError, AttributeError):
                # Event loop closing during shutdown
                dead.append(queue)

        for q in dead:
            self._unsubscribe(user_id, topic, q)

    async def broadcast_to_vault(
        self,
        _vault_id: UUID,
        topic: str,
        data: dict[str, Any],
        user_ids: list[UUID],
    ) -> None:
        """Publish the same event to all users in a vault.

        Args:
            vault_id: Vault UUID (unused, kept for API compatibility).
            topic: Event topic.
            data: Event payload.
            user_ids: List of user UUIDs to broadcast to.
        """
        await asyncio.gather(*[self.publish(uid, topic, data) for uid in user_ids])

    async def close(self) -> None:
        """Shut down all subscribers by sending None sentinels."""
        for _topic, user_map in list(self._subscribers.items()):
            for _user_id, queues in list(user_map.items()):
                for queue in list(queues):
                    # Drain one item at a time to make room for the sentinel,
                    # without stealing data from concurrent subscribers.
                    for _ in range(self._queue_maxsize + 1):
                        try:
                            queue.put_nowait(None)
                            break
                        except asyncio.QueueFull:
                            with contextlib.suppress(asyncio.QueueEmpty):
                                queue.get_nowait()
                queues.clear()
            user_map.clear()
        self._subscribers.clear()
        logger.info("SSE manager shut down, all subscribers cleared")


# Global singleton — mirrors websocket_manager.manager
sse_manager = SSEManager()
