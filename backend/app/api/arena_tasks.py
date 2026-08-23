"""Arena tick actor - kept in its own module so endpoints can wake it safely.

Importing ``app.api.tasks`` from an endpoint creates a circular import chain
(``tasks`` -> ``crud.pregnancy`` -> ``app.api.deps``), so the fast arena tick
lives here with only lightweight imports.
"""

import asyncio
import logging
from typing import Final

import dramatiq
import periodiq

import app.core.dramatiq  # ruff: ignore[unused-import] — broker must be set before the actor registers
from app.core.game_config import game_config
from app.db.session import task_session
from app.services.tick_chain import claim_tick_chain

logger = logging.getLogger(__name__)
ARENA_TICK_CHAIN_KEY: Final = "fallout:arena-tick:chain"


async def _run_arena_tick(chain_token: str | None) -> tuple[str | None, dict | None]:
    """Claim the tick chain, then run one fight round across all arena rooms.

    Returns ``(next_chain_token, stats)``, or ``(None, None)`` when the chain
    lease was lost to another worker (the periodiq watchdog will re-seed it).
    """
    from redis.asyncio import Redis

    from app.core.config import settings
    from app.services.arena_service import arena_service

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        claimed_token = await claim_tick_chain(redis, ARENA_TICK_CHAIN_KEY, chain_token)
        if claimed_token is None:
            return None, None

        async with task_session() as session:
            stats = await arena_service.process_arena_ticks(session, game_config.game_loop.arena_tick_seconds)
        return claimed_token, stats
    finally:
        await redis.close()


@dramatiq.actor(actor_name="arena_tick", max_retries=0)
def arena_tick(chain_token: str | None = None):
    """Fast arena fight tick - processes fight-ready arenas across all vaults.

    Reschedules itself every ``arena_tick_seconds`` while holding a Redis
    chain lease (periodiq 6-field crons only resolve at minute granularity),
    so combat updates read as live instead of once per minute. The periodiq
    cron below acts as a low-frequency watchdog that re-seeds the chain if it
    ever dies or the lease expires.
    """
    next_chain_token = None
    try:
        next_chain_token, stats = asyncio.run(_run_arena_tick(chain_token))
    except Exception:
        logger.exception("Arena tick failed")
    else:
        if stats is not None and stats["arena"]["rounds"]:
            logger.info(f"Arena tick completed: {stats}")
    finally:
        if next_chain_token is not None:
            arena_tick.send_with_options(
                args=(next_chain_token,),
                delay=game_config.game_loop.arena_tick_seconds * 1000,
            )


arena_tick.options["periodic"] = periodiq.cron("*/2 * * * *")
