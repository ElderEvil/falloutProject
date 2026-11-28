"""Combat Zone tick actor — its own module so the scheduler adapter can wake it.

Mirrors ``app/api/arena_tasks.py``: the scheduler imports this module lazily, and
the actor only imports lightweight modules until the task body runs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

import dramatiq
import periodiq

import app.core.dramatiq  # ruff: ignore[unused-import] — broker must be set before the actor registers
from app.core.async_runtime import run_async
from app.core.chained_tick import run_chained_tick
from app.core.combat_zone_dispatch import register_combat_zone_wake
from app.core.game_config import game_config

if TYPE_CHECKING:
    from app.services.combat.combat_zone_engine import CombatZoneTickStats

logger = logging.getLogger(__name__)
COMBAT_ZONE_TICK_CHAIN_KEY: Final = "fallout:combat-zone-tick:chain"


async def _run_combat_zone_tick(chain_token: str | None) -> tuple[str | None, CombatZoneTickStats | None]:
    """Claim the chain, then advance every party and match by one micro-round."""
    from app.services.combat.combat_zone_service import combat_zone_service

    return await run_chained_tick(
        COMBAT_ZONE_TICK_CHAIN_KEY,
        chain_token,
        lambda session: combat_zone_service.process_ticks(session, game_config.combat_zone.tick_seconds),
    )


@dramatiq.actor(actor_name="combat_zone_tick", max_retries=0)
def combat_zone_tick(chain_token: str | None = None):
    """Resolve one Combat Zone micro-round every ``tick_seconds`` while the feature is on.

    The chain lease keeps a single 2 s loop alive; the periodiq cron is only a
    watchdog that re-seeds it or takes over a stale lease. A disabled switch drains
    outstanding parties instead of stopping the chain, so the lease outlives them.
    """
    next_chain_token = None
    stats = None
    try:
        next_chain_token, stats = run_async(_run_combat_zone_tick(chain_token))
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
        if next_chain_token is not None and (game_config.combat_zone.enabled or (stats and stats.pending)):
            delay_ms = game_config.combat_zone.tick_seconds * 1000
            logger.debug("Rescheduling combat_zone_tick in %d ms", delay_ms)
            combat_zone_tick.send_with_options(
                args=(next_chain_token,),
                delay=delay_ms,
            )


combat_zone_tick.options["periodic"] = periodiq.cron("*/2 * * * *")
register_combat_zone_wake(combat_zone_tick.send)
