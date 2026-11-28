"""Arena tick actor, isolated so endpoints can wake it safely.

Importing app.api.tasks from an endpoint creates a circular import chain
(tasks -> crud.pregnancy -> app.api.deps).
"""

import logging
from typing import Final

import dramatiq
import periodiq

import app.core.dramatiq  # ruff: ignore[unused-import] — broker must be set before the actor registers
from app.core.async_runtime import run_async
from app.core.chained_tick import run_chained_tick
from app.core.game_config import game_config

logger = logging.getLogger(__name__)
ARENA_TICK_CHAIN_KEY: Final = "fallout:arena-tick:chain"


async def _run_arena_tick(chain_token: str | None) -> tuple[str | None, dict | None]:
    """Claim the chain and run one fight round across all arena rooms."""
    from app.services.combat.arena_service import arena_service

    return await run_chained_tick(
        ARENA_TICK_CHAIN_KEY,
        chain_token,
        lambda session: arena_service.process_arena_ticks(session, game_config.game_loop.arena_tick_seconds),
    )


@dramatiq.actor(actor_name="arena_tick", max_retries=0)
def arena_tick(chain_token: str | None = None):
    """Fast arena fight tick across all vaults.

    Self-reschedules every arena_tick_seconds because periodiq crons only
    resolve at minute granularity. The cron below is a watchdog: re-seeds a
    dead chain, takes over once its heartbeat expires.
    """
    next_chain_token = None
    try:
        next_chain_token, stats = run_async(_run_arena_tick(chain_token))
    except Exception:
        logger.exception("Arena tick failed")
    else:
        if stats is not None and stats["arena"]["rounds"]:
            logger.info(f"Arena tick completed: {stats}")
    finally:
        if next_chain_token is not None:
            delay_ms = game_config.game_loop.arena_tick_seconds * 1000
            logger.debug("Rescheduling arena_tick in %d ms", delay_ms)
            arena_tick.send_with_options(
                args=(next_chain_token,),
                delay=delay_ms,
            )


arena_tick.options["periodic"] = periodiq.cron("*/2 * * * *")
