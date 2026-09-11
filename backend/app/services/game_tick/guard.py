"""Failure-isolation policy for per-entity steps inside tick phases.

Tick sweeps must survive single bad entities: one corrupt exploration or
training session cannot abort the whole pass. This helper is the only
sanctioned shape for that — call it instead of nesting try/except blocks.
"""

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def guard_phase(
    label: str,
    fn: Callable[[], Awaitable[None]],
    *,
    catch: tuple[type[BaseException], ...],
) -> str | None:
    """Run a per-entity tick step; return the error message, or None on success."""
    try:
        await fn()
    except catch as e:
        logger.error(f"{label}: {e}", exc_info=True)
        return str(e)
    else:
        return None
