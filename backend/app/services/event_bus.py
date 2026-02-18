"""Event bus service providing pub/sub functionality for game events.

Enables decoupled communication between game systems. Services emit events
when actions occur, and evaluators subscribe to track objective progress.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine
from enum import StrEnum
from typing import Any

from pydantic import UUID4

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, UUID4, dict[str, Any]], Coroutine[Any, Any, None]]


class GameEvent(StrEnum):
    RESOURCE_COLLECTED = "resource_collected"
    ROOM_BUILT = "room_built"
    ROOM_UPGRADED = "room_upgraded"
    DWELLER_TRAINED = "dweller_trained"
    DWELLER_ASSIGNED = "dweller_assigned"
    DWELLER_ASSIGNED_CORRECTLY = "dweller_assigned_correctly"
    DWELLER_LEVEL_UP = "dweller_level_up"
    ITEM_COLLECTED = "item_collected"
    QUEST_COMPLETED = "quest_completed"
    OBJECTIVE_COMPLETED = "objective_completed"


class EventBus:
    """In-memory pub/sub event bus for game events.

    Handlers are async callables: ``(event_type, vault_id, data) -> None``.
    Errors in individual handlers are logged but don't break other handlers.

    Usage::

        event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, on_resource_collected)
        await event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": "caps", "amount": 100})
    """

    def __init__(self) -> None:
        self._handlers: dict[GameEvent, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: GameEvent, handler: EventHandler) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Handler '{handler.__name__}' subscribed to {event_type}")

    async def emit(self, event_type: GameEvent, vault_id: UUID4, data: dict[str, Any]) -> None:
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.debug(f"[EVENT] No handlers for {event_type}, skipping (vault: {vault_id})")
            return

        logger.info(f"[EVENT] Emitting {event_type} for vault {vault_id} to {len(handlers)} handler(s): {data}")
        logger.debug(f"[EVENT] Handlers: {[h.__name__ for h in handlers]}")

        results = await asyncio.gather(
            *[self._safe_call(handler, event_type, vault_id, data) for handler in handlers],
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.exception(
                    f"Handler '{handlers[i].__name__}' failed for {event_type}: {result}",
                    exc_info=result,
                )

    def unsubscribe(self, event_type: GameEvent, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type, [])
        try:
            handlers.remove(handler)
            logger.debug(f"Handler '{handler.__name__}' unsubscribed from {event_type}")
        except ValueError:
            logger.warning(f"Handler '{handler.__name__}' was not subscribed to {event_type}")

    def clear(self) -> None:
        self._handlers.clear()
        logger.debug("All event handlers cleared")

    @staticmethod
    async def _safe_call(handler: EventHandler, event_type: GameEvent, vault_id: UUID4, data: dict[str, Any]) -> None:
        await handler(event_type, vault_id, data)


event_bus = EventBus()
