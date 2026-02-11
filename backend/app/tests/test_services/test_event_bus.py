"""Tests for EventBus."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services.event_bus import EventBus, GameEvent


@pytest.fixture
def fresh_event_bus():
    """Create a fresh EventBus instance for testing."""
    bus = EventBus()
    yield bus
    bus.clear()


@pytest.mark.asyncio
async def test_subscribe_handler(fresh_event_bus: EventBus) -> None:
    """Test handler is registered."""
    handler = AsyncMock()

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler)

    assert handler in fresh_event_bus._handlers[GameEvent.RESOURCE_COLLECTED]


@pytest.mark.asyncio
async def test_subscribe_duplicate_handler(fresh_event_bus: EventBus) -> None:
    """Test duplicate handler not added twice."""
    handler = AsyncMock()

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler)
    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler)

    assert len(fresh_event_bus._handlers[GameEvent.RESOURCE_COLLECTED]) == 1


@pytest.mark.asyncio
async def test_emit_calls_handler(fresh_event_bus: EventBus) -> None:
    """Test handler is called on emit."""
    handler = AsyncMock()
    vault_id = "test-vault-id"

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler)
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"amount": 100})

    handler.assert_called_once()
    call_args = handler.call_args[0]
    assert call_args[0] == GameEvent.RESOURCE_COLLECTED
    assert call_args[1] == vault_id


@pytest.mark.asyncio
async def test_emit_with_data(fresh_event_bus: EventBus) -> None:
    """Test data is passed correctly."""
    handler = AsyncMock()
    vault_id = "test-vault-id"
    data = {"resource_type": "caps", "amount": 100}

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler)
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, data)

    call_args = handler.call_args[0]
    assert call_args[2] == data


@pytest.mark.asyncio
async def test_emit_multiple_handlers(fresh_event_bus: EventBus) -> None:
    """Test all handlers called."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()
    vault_id = "test-vault-id"

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler1)
    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler2)
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {})

    handler1.assert_called_once()
    handler2.assert_called_once()


@pytest.mark.asyncio
async def test_emit_no_handlers(fresh_event_bus: EventBus) -> None:
    """Test no error when no handlers."""
    vault_id = "test-vault-id"

    # Should not raise
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {})


@pytest.mark.asyncio
async def test_emit_handler_error(fresh_event_bus: EventBus) -> None:
    """Test other handlers still called when one fails."""
    failing_handler = AsyncMock(side_effect=Exception("Handler error"))
    good_handler = AsyncMock()
    vault_id = "test-vault-id"

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, failing_handler)
    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, good_handler)

    # Should not raise even though one handler fails
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {})

    good_handler.assert_called_once()


@pytest.mark.asyncio
async def test_unsubscribe_handler(fresh_event_bus: EventBus) -> None:
    """Test handler removed."""
    handler = AsyncMock()

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler)
    fresh_event_bus.unsubscribe(GameEvent.RESOURCE_COLLECTED, handler)

    assert handler not in fresh_event_bus._handlers[GameEvent.RESOURCE_COLLECTED]


@pytest.mark.asyncio
async def test_unsubscribe_not_subscribed(fresh_event_bus: EventBus) -> None:
    """Test no error when unsubscribing not-subscribed handler."""
    handler = AsyncMock()

    # Should not raise
    fresh_event_bus.unsubscribe(GameEvent.RESOURCE_COLLECTED, handler)


@pytest.mark.asyncio
async def test_clear_handlers(fresh_event_bus: EventBus) -> None:
    """Test all handlers removed."""
    handler1 = AsyncMock()
    handler2 = AsyncMock()

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler1)
    fresh_event_bus.subscribe(GameEvent.ROOM_BUILT, handler2)
    fresh_event_bus.clear()

    assert len(fresh_event_bus._handlers) == 0


@pytest.mark.asyncio
async def test_event_bus_singleton() -> None:
    """Test singleton instance."""
    from app.services.event_bus import event_bus as bus1
    from app.services.event_bus import event_bus as bus2

    assert bus1 is bus2


@pytest.mark.asyncio
async def test_concurrent_emits(fresh_event_bus: EventBus) -> None:
    """Test concurrent emits handled correctly."""
    handler = AsyncMock()

    fresh_event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, handler)

    # Emit multiple events concurrently
    await asyncio.gather(
        fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, "vault1", {"amount": 100}),
        fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, "vault2", {"amount": 200}),
        fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, "vault3", {"amount": 300}),
    )

    assert handler.call_count == 3
