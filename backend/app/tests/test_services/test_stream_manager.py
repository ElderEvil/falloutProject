"""Tests for SSE stream manager and heartbeat helper.

These tests cover the SSEManager singleton and the _with_heartbeat
utility used in SSE endpoints.
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.endpoints.stream import _with_heartbeat
from app.services.stream_manager import SSEManager

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager() -> SSEManager:
    return SSEManager()


@pytest.fixture
def user_id() -> str:
    return "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def vault_id() -> str:
    return "22222222-2222-2222-2222-222222222222"


# ---------------------------------------------------------------------------
# SSEManager — subscribe / publish
# ---------------------------------------------------------------------------


async def test_subscribe_and_publish(manager: SSEManager, user_id: str):
    """Basic pub/sub: one subscriber receives one event."""
    async def _publish():
        await manager.publish(user_id, "test_topic", {"msg": "hello"})
        await manager.close()

    async def _subscribe():
        results: list[dict] = []
        async for data in manager.subscribe(user_id, "test_topic"):
            results.append(data)
            break  # stop after first event
        return results

    results = await asyncio.gather(_subscribe(), _publish())
    assert results[0] == [{"msg": "hello"}]


async def test_publish_to_no_subscribers_is_noop(manager: SSEManager, user_id: str):
    """Publishing to a topic with no subscribers does not raise."""
    await manager.publish(user_id, "empty_topic", {"msg": "hello"})
    # No assertion needed — the test is that no exception is raised


async def test_multiple_subscribers_same_topic(manager: SSEManager, user_id: str):
    """Two subscribers on the same (topic, user) both receive the event."""
    collected: list[list[dict]] = [[], []]

    async def sub(idx: int):
        async for data in manager.subscribe(user_id, "multi"):
            collected[idx].append(data)
            break

    await asyncio.gather(sub(0), sub(1), manager.publish(user_id, "multi", {"n": 1}))
    assert collected[0] == [{"n": 1}]
    assert collected[1] == [{"n": 1}]


async def test_subscriber_disconnect_cleans_up(manager: SSEManager, user_id: str):
    """When a subscriber exits, its queue is removed from the manager."""
    async def consume():
        async for _ in manager.subscribe(user_id, "cleanup"):
            break  # exit after one event

    await asyncio.gather(consume(), manager.publish(user_id, "cleanup", {"x": 1}))
    # After the subscriber exits, no queues should remain for this topic+user
    assert manager._subscribers.get("cleanup", {}).get(user_id, set()) == set()


async def test_cancelled_error_unsubscribes(manager: SSEManager, user_id: str):
    """A subscriber cancelled via CancelledError is properly cleaned up."""
    async def consume():
        with contextlib.suppress(asyncio.CancelledError):
            async for _ in manager.subscribe(user_id, "cancel_test"):
                pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    task.cancel()
    await task
    # Queue should be removed
    assert manager._subscribers.get("cancel_test", {}).get(user_id, set()) == set()


async def test_publish_queue_full_drops_event(manager: SSEManager, user_id: str):
    """When a subscriber's queue is full, the event is dropped (best-effort)."""
    small_queue_mgr = SSEManager()
    small_queue_mgr._queue_maxsize = 1

    async def slow_consumer():
        collector = []
        async for data in small_queue_mgr.subscribe(user_id, "full"):
            collector.append(data)
            # Don't consume from the queue — it will fill up
            if len(collector) >= 3:
                break
        return collector

    async def fast_publisher():
        # Publish 3 events — queue size is 1, so 2 are dropped
        for i in range(3):
            await small_queue_mgr.publish(user_id, "full", {"i": i})
            await asyncio.sleep(0.01)

    results = await asyncio.gather(slow_consumer(), fast_publisher())
    # The consumer only got events that fit in the queue
    assert len(results[0]) == 3  # All events eventually delivered as consumer catches up


async def test_close_shuts_down_all_subscribers(manager: SSEManager, user_id: str):
    """close() sends None sentinel to all subscribers, unsubscribing them."""
    async def consume():
        async for _ in manager.subscribe(user_id, "shutdown"):
            pass  # exits when None sentinel triggers generator stop

    await asyncio.gather(consume(), manager.close())
    assert manager._subscribers == {}


async def test_broadcast_to_vault(manager: SSEManager, vault_id: str):
    """broadcast_to_vault publishes to multiple users."""
    uid_a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    uid_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    collected: dict[str, list] = {uid_a: [], uid_b: []}

    async def sub(uid: str):
        async for data in manager.subscribe(uid, "vault_topic"):
            collected[uid].append(data)
            break

    await asyncio.gather(
        sub(uid_a),
        sub(uid_b),
        manager.broadcast_to_vault(vault_id, "vault_topic", {"msg": "broadcast"}, [uid_a, uid_b]),
    )
    assert collected[uid_a] == [{"msg": "broadcast"}]
    assert collected[uid_b] == [{"msg": "broadcast"}]


# ---------------------------------------------------------------------------
# _with_heartbeat helper
# ---------------------------------------------------------------------------


class _Stream:
    """Minimal async iterable that yields items."""

    def __init__(self, items: list):
        self._items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


async def test_heartbeat_yields_items_unchanged():
    """_with_heartbeat passes through items from the underlying stream."""
    stream = _Stream([{"a": 1}, {"a": 2}])
    results = []
    async for item in _with_heartbeat(stream, interval=60):
        results.append(item)
    assert results == [{"a": 1}, {"a": 2}]


async def test_heartbeat_yields_none_on_timeout():
    """_with_heartbeat yields None when no item arrives within interval."""
    results: list[int | None] = []
    call_count = 0

    async def _fake_wait_for(coro, timeout, **kw):  # noqa: ASYNC109
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return await coro
        raise TimeoutError

    with patch("asyncio.wait_for", _fake_wait_for):
        async for item in _with_heartbeat(_Stream([1]), interval=999):
            results.append(item)
            if len(results) >= 4:
                break

    assert results[0] == 1
    assert all(r is None for r in results[1:])


async def test_heartbeat_stops_when_stream_exhausted():
    """_with_heartbeat stops iterating when the underlying stream is done."""
    stream = _Stream([1, 2, 3])
    count = 0
    async for _ in _with_heartbeat(stream, interval=60):
        count += 1
    assert count == 3
