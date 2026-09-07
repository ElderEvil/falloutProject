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


# No assertion needed — the test is that no exception is raised


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
    results = [item async for item in _with_heartbeat(stream, interval=60)]
    assert results == [{"a": 1}, {"a": 2}]


async def test_heartbeat_yields_none_on_timeout():
    """_with_heartbeat yields None when no item arrives within interval."""
    results: list[int | None] = []
    call_count = 0

    async def _fake_wait(tasks, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(0)
            return set(tasks), set()
        return set(), set()

    with patch("asyncio.wait", _fake_wait):
        async for item in _with_heartbeat(_Stream([1]), interval=999):
            results.append(item)
            if len(results) >= 4:
                break

    assert results[0] == 1
    assert all(r is None for r in results[1:])
