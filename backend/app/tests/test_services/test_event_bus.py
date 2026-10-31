"""Tests for EventBus."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.event_bus import EventBus, GameEvent


@pytest.fixture
def fresh_event_bus():
    """Create a fresh EventBus instance for testing."""
    bus = EventBus()
    yield bus
    bus.clear()


@pytest.mark.asyncio
async def test_unsubscribe_not_subscribed(fresh_event_bus: EventBus) -> None:
    """Test no error when unsubscribing not-subscribed handler."""
    handler = AsyncMock()

    # Should not raise
    fresh_event_bus.unsubscribe(GameEvent.RESOURCE_COLLECTED, handler)


@pytest.mark.asyncio
async def test_event_bus_singleton() -> None:
    """Test singleton instance."""
    from app.core.event_bus import event_bus as bus1
    from app.core.event_bus import event_bus as bus2

    assert bus1 is bus2


@pytest.mark.asyncio
async def test_clear_locks_only_removes_the_given_loop(fresh_event_bus: EventBus) -> None:
    """Concurrent actors must not clear each other's emit locks."""
    vault_id = uuid4()
    current = (GameEvent.RESOURCE_COLLECTED, vault_id, 1)
    other = (GameEvent.RESOURCE_COLLECTED, vault_id, 2)
    fresh_event_bus._emit_locks[current] = asyncio.Lock()
    fresh_event_bus._emit_locks[other] = asyncio.Lock()

    fresh_event_bus.clear_locks(1)

    assert current not in fresh_event_bus._emit_locks
    assert other in fresh_event_bus._emit_locks
