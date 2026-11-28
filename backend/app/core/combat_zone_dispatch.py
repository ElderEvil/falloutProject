"""Combat Zone tick-wake dispatch.

Services own the decision to wake the tick, but must not import the API layer.
The composition roots (``main.py`` for the web process, ``app.api.tasks`` for the
worker) bind the actor's ``send`` here; without a binding the periodiq watchdog
still seeds a dead chain, so a missing binding degrades to a delay, not a failure.
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

_combat_zone_wake: list[Callable[[], object]] = []


def register_combat_zone_wake(wake: Callable[[], object]) -> None:
    """Bind the transport-specific wake (called once at composition time)."""
    _combat_zone_wake[:] = [wake]


def request_combat_zone_tick() -> None:
    """Best-effort wake; the watchdog covers a missing or failed binding."""
    if not _combat_zone_wake:
        logger.debug("Combat Zone tick wake is not bound; waiting for the watchdog")
        return
    try:
        _combat_zone_wake[0]()
    except Exception:
        logger.exception("Could not wake the Combat Zone tick; the watchdog will seed it")
