"""Combat Zone tick-wake dispatch.

Services own the decision to wake the tick, but must not import the API layer.
The composition roots (``main.py`` for the web process, ``app.api.tasks`` for the
worker) bind the actor's ``send`` here; without a binding the periodiq watchdog
still seeds a dead chain, so a missing binding degrades to a delay, not a failure.
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

_combat_zone_wake: Callable[[], None] | None = None


def register_combat_zone_wake(wake: Callable[[], None]) -> None:
    """Bind the transport-specific wake (called once at composition time)."""
    global _combat_zone_wake
    _combat_zone_wake = wake


def request_combat_zone_tick() -> None:
    """Best-effort wake; the watchdog covers a missing or failed binding."""
    if _combat_zone_wake is None:
        logger.debug("Combat Zone tick wake is not bound; waiting for the watchdog")
        return
    try:
        _combat_zone_wake()
    except Exception:
        logger.exception("Could not wake the Combat Zone tick; the watchdog will seed it")
