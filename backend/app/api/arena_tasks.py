"""Arena tick actor - kept in its own module so endpoints can wake it safely.

Importing ``app.api.tasks`` from an endpoint creates a circular import chain
(``tasks`` -> ``crud.pregnancy`` -> ``app.api.deps``), so the fast arena tick
lives here with only lightweight imports.
"""

import asyncio
import logging

import dramatiq
import periodiq

import app.core.dramatiq  # ruff: ignore[unused-import] — broker must be set before the actor registers
from app.core.game_config import game_config
from app.db.session import task_session

logger = logging.getLogger(__name__)


async def _run_arena_tick() -> dict:
    """Run one fight round for every fight-ready arena room across all vaults."""
    from app.services.arena_service import arena_service

    async with task_session() as session:
        return await arena_service.process_arena_ticks(session, game_config.game_loop.arena_tick_seconds)


@dramatiq.actor(actor_name="arena_tick", max_retries=0)
def arena_tick():
    """Fast arena fight tick - processes fight-ready arenas across all vaults.

    Reschedules itself every ``arena_tick_seconds`` (periodiq 6-field crons
    only resolve at minute granularity), so combat updates read as live instead
    of once per minute. The periodiq cron below acts as a low-frequency
    watchdog that re-seeds the loop if it ever dies.
    """
    try:
        stats = asyncio.run(_run_arena_tick())
    except Exception:
        logger.exception("Arena tick failed")
    else:
        if stats["arena"]["rounds"]:
            logger.info(f"Arena tick completed: {stats}")
    finally:
        arena_tick.send_with_options(delay=game_config.game_loop.arena_tick_seconds * 1000)


arena_tick.options["periodic"] = periodiq.cron("*/2 * * * *")
