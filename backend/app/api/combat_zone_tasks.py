"""Combat Zone tick actor — its own module so the scheduler adapter can wake it.

Mirrors ``app/api/arena_tasks.py``: the scheduler imports this module lazily, and
the actor only imports lightweight modules until the task body runs.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Final

import dramatiq
import periodiq

import app.core.dramatiq  # ruff: ignore[unused-import] — broker must be set before the actor registers
from app.core.combat_zone_dispatch import register_combat_zone_wake
from app.core.game_config import game_config
from app.db.session import task_session
from app.services.tick_chain import claim_tick_chain

if TYPE_CHECKING:
    from app.services.combat.combat_zone_engine import CombatZoneTickStats

logger = logging.getLogger(__name__)
COMBAT_ZONE_TICK_CHAIN_KEY: Final = "fallout:combat-zone-tick:chain"


async def _run_combat_zone_tick(chain_token: str | None) -> tuple[str | None, CombatZoneTickStats | None]:
    """Claim the chain, then advance every party and match by one micro-round."""
    from redis.asyncio import Redis

    from app.core.config import settings
    from app.services.combat.combat_zone_service import combat_zone_service

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        claimed_token = await claim_tick_chain(redis, COMBAT_ZONE_TICK_CHAIN_KEY, chain_token)
        if claimed_token is None:
            return None, None

        async with task_session() as session:
            stats = await combat_zone_service.process_ticks(session, game_config.combat_zone.tick_seconds)
        return claimed_token, stats
    finally:
        await redis.close()


@dramatiq.actor(actor_name="combat_zone_tick", max_retries=0)
def combat_zone_tick(chain_token: str | None = None):
    """Resolve one Combat Zone micro-round every ``tick_seconds`` while the feature is on.

    The chain lease keeps a single 2 s loop alive; the periodiq cron is only a
    watchdog that re-seeds it or takes over a stale lease.
    """
    if not game_config.combat_zone.enabled:
        return

    next_chain_token = None
    try:
        next_chain_token, stats = asyncio.run(_run_combat_zone_tick(chain_token))
    except Exception:
        logger.exception("Combat Zone tick failed")
    else:
        if stats is not None and stats.matches:
            logger.info(
                "Combat Zone tick: matches=%d paired=%d arrived=%d returned=%d skipped=%s",
                stats.matches,
                stats.paired,
                stats.arrived,
                stats.returned,
                stats.skipped,
            )
    finally:
        if next_chain_token is not None:
            delay_ms = game_config.combat_zone.tick_seconds * 1000
            logger.debug("Rescheduling combat_zone_tick in %d ms", delay_ms)
            combat_zone_tick.send_with_options(
                args=(next_chain_token,),
                delay=delay_ms,
            )


combat_zone_tick.options["periodic"] = periodiq.cron("*/2 * * * *")
register_combat_zone_wake(combat_zone_tick.send)
