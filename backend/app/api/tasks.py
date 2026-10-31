"""Dramatiq task actors for scheduled game processing."""

import asyncio
import logging
import sys
import time
from typing import Final
from uuid import UUID, uuid4

import dramatiq
import periodiq
from redis.asyncio import Redis

import app.api.arena_tasks  # ruff: ignore[unused-import] - registers the arena_tick watchdog cron
import app.core.dramatiq  # ruff: ignore[unused-import] — ensures broker is configured when dramatiq CLI imports this module
from app.core.config import settings
from app.core.event_bus import event_bus
from app.core.game_config import game_config
from app.core.tick_chain import claim_tick_chain
from app.db.session import task_session
from app.services.cleanup_service import cleanup_service
from app.services.family.death_service import death_service
from app.services.game_loop_service import game_loop_service
from app.services.game_tick.guard import recover_session
from app.services.game_tick.tick_results import VaultTickResult
from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)
INCIDENT_TICK_CHAIN_KEY: Final = "fallout:incident-tick:chain"
VAULT_TICK_LOCK_PREFIX: Final = "fallout:vault-tick:"
VAULT_TICK_LOCK_TTL_SECONDS: Final = game_config.game_loop.tick_interval - 5
VAULT_TICK_LOCK_RELEASE_SCRIPT: Final = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@dramatiq.actor(actor_name="create_task")
def create_task(task_time: int):
    """Simulate a long-running task for testing.

    Args:
        task_time: Duration in seconds to sleep.

    Returns:
        True when the task completes.
    """
    time.sleep(task_time)
    return True


async def _dispatch_game_tick() -> dict[str, int | float]:
    async with task_session() as session:
        vault_ids = await game_loop_service.get_active_vault_ids(session)
    for vault_id in vault_ids:
        process_vault_tick.send(str(vault_id))
    return {"vaults_dispatched": len(vault_ids)}


@dramatiq.actor(actor_name="game_tick", max_retries=3, min_backoff=60000)
def game_tick():
    """Dispatch one vault tick per active vault. Scheduled every 60 seconds."""
    start = time.perf_counter()
    try:
        logger.info("Dispatching game tick")
        stats: dict[str, int | float] = asyncio.run(_dispatch_game_tick())
    except Exception:
        logger.exception("Game tick dispatch failed")
        raise
    stats["dispatch_time"] = round(time.perf_counter() - start, 3)
    logger.info(f"Game tick dispatched: {stats}")
    return stats


async def _run_incident_tick(chain_token: str | None) -> tuple[str | None, dict[str, int] | None]:
    """Claim the tick chain, then process one round of incident combat.

    Returns ``(next_chain_token, stats)``, or ``(None, None)`` when the chain
    lease was lost to another worker (the periodiq watchdog will re-seed it,
    taking over a stale lease once its heartbeat expires). A processing failure
    logs the error but still returns the claimed token, so the chain keeps
    self-scheduling instead of stalling until lease expiry.
    """
    from app.services.combat.incident_service import incident_service

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        claimed_token = await claim_tick_chain(redis, INCIDENT_TICK_CHAIN_KEY, chain_token)
        if claimed_token is None:
            return None, None

        try:
            async with task_session() as session:
                stats = await incident_service.process_all_vaults_incidents(
                    session, game_config.game_loop.incident_tick_seconds
                )
        except Exception:
            logger.exception("Incident processing failed")
            stats = None
        return claimed_token, stats
    finally:
        await redis.close()


@dramatiq.actor(actor_name="incident_tick", max_retries=0)
def incident_tick(chain_token: str | None = None):
    """Fast incident tick - processes combat for every vault's active incidents.

    Self-reschedules every ``incident_tick_seconds`` (independent of the 60s
    game tick) so incident combat gives live feedback. A Redis lease plus a
    short-TTL heartbeat lets the periodiq cron below act as a watchdog that
    re-seeds the chain when it dies and takes over a stale lease once its
    heartbeat expires, instead of waiting out the lease TTL.
    """
    next_chain_token = None
    try:
        next_chain_token, stats = asyncio.run(_run_incident_tick(chain_token))
    except Exception:
        logger.exception("Incident tick failed")
    else:
        if stats is not None and (stats["resolved"] or stats["spawned"]):
            logger.info(f"Incident tick completed: {stats}")
    finally:
        if next_chain_token is not None:
            delay_ms = game_config.game_loop.incident_tick_seconds * 1000
            logger.debug("Rescheduling incident_tick in %d ms", delay_ms)
            incident_tick.send_with_options(
                args=(next_chain_token,),
                delay=delay_ms,
            )


async def _acquire_vault_tick_lock(redis: Redis, vault_id: str) -> str | None:
    token = uuid4().hex
    acquired = await redis.set(f"{VAULT_TICK_LOCK_PREFIX}{vault_id}", token, nx=True, ex=VAULT_TICK_LOCK_TTL_SECONDS)
    return token if acquired else None


async def _release_vault_tick_lock(redis: Redis, vault_id: str, token: str) -> None:
    await redis.eval(VAULT_TICK_LOCK_RELEASE_SCRIPT, 1, f"{VAULT_TICK_LOCK_PREFIX}{vault_id}", token)


async def _process_vault_tick_async(vault_id: str, redis: Redis) -> VaultTickResult:
    loop_id = id(asyncio.get_running_loop())
    token = await _acquire_vault_tick_lock(redis, vault_id)
    if token is None:
        return {"status": "skipped"}
    succeeded = False
    try:
        from app.services.progression.objectives.evaluators import evaluator_manager
        from app.services.progression.objectives.notifications import register_objective_event_handlers

        evaluator_manager.initialize()
        register_objective_event_handlers()

        async with task_session() as session:
            result = await game_loop_service.process_vault_tick(session, UUID(vault_id))
    except ResourceNotFoundException:
        logger.warning(f"Vault {vault_id} no longer exists; skipping tick")
        return {"status": "missing"}
    else:
        succeeded = True
        return result
    finally:
        if not succeeded:
            await _release_vault_tick_lock(redis, vault_id, token)
        event_bus.clear_locks(loop_id)


@dramatiq.actor(actor_name="process_vault_tick", max_retries=3, min_backoff=30000)
def process_vault_tick(vault_id: str):
    """Process one vault tick under a per-vault Redis lease."""
    start = time.perf_counter()

    async def run_vault_tick():
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            return await _process_vault_tick_async(vault_id, redis)
        finally:
            await redis.aclose()

    try:
        result = asyncio.run(run_vault_tick())
    except Exception:
        logger.exception(f"Vault {vault_id} tick failed")
        raise
    if result.get("status") in {"skipped", "missing"}:
        logger.info(f"Vault {vault_id} tick {result['status']}")
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Vault {vault_id} tick completed in {elapsed_ms:.1f}ms")
    return result


async def _check_permanent_deaths() -> int:
    """Mark dead dwellers past the revival window as permanently dead."""
    async with task_session() as session:
        count = await death_service.check_and_mark_permanent_deaths(session)
        await session.commit()
        return count


@dramatiq.actor(actor_name="check_permanent_deaths", max_retries=3, min_backoff=3600000)
def check_permanent_deaths():
    """Check for dead dwellers past the revival window and mark them as permanently dead.

    Returns:
        dict: Count of dwellers marked as permanently dead.
    """
    try:
        count = asyncio.run(_check_permanent_deaths())
    except Exception:
        logger.exception("Permanent death check failed")
        raise
    else:
        logger.info(f"Permanent death check completed: {count} dwellers marked as permanently dead")
        return {"marked_permanently_dead": count}


async def _check_quest_completion() -> int:
    """Auto-complete quests that have exceeded their duration."""
    from app.services.progression.quests.service import quest_service

    async with task_session() as session:
        count = await quest_service.check_and_complete_quests(session)
        await session.commit()
        return count


@dramatiq.actor(actor_name="check_quest_completion", max_retries=3, min_backoff=300000)
def check_quest_completion():
    """Check for quests that have exceeded their duration and auto-complete them.

    Returns:
        dict: Count of quests auto-completed.
    """
    try:
        count = asyncio.run(_check_quest_completion())
    except Exception:
        logger.exception("Quest completion check failed")
        raise
    else:
        logger.info(f"Quest completion check completed: {count} quests auto-completed")
        return {"quests_completed": count}


async def _check_location_reclears() -> int:
    """Null elapsed reclear windows and notify owners the point is ready again."""
    from app.services.map_service import map_service

    async with task_session() as session:
        try:
            return await map_service.sweep_reclears(session)
        except Exception:
            await recover_session(session)
            raise


@dramatiq.actor(actor_name="check_location_reclears", max_retries=3, min_backoff=300000)
def check_location_reclears():
    """Check for map points whose reclear window has elapsed and notify their owners.

    Returns:
        dict: Count of map points swept.
    """
    try:
        count = asyncio.run(_check_location_reclears())
    except Exception:
        logger.exception("Location reclear check failed")
        raise
    else:
        logger.info(f"Location reclear check completed: {count} points ready")
        return {"reclears_swept": count}


async def _refresh_objectives() -> dict:
    """Refresh due categories for every non-deleted vault through the shared UTC policy."""
    from app.crud.vault import vault as vault_crud
    from app.services.progression.objectives.refresh_service import ensure_current_objectives

    async with task_session() as session:
        vault_ids = await vault_crud.get_non_deleted_ids(session)
        refreshed_count = 0
        for vault_id in vault_ids:
            try:
                refreshed_count += len(await ensure_current_objectives(session, vault_id))
            except Exception:
                await recover_session(session)
                logger.exception("Objective refresh failed for vault %s", vault_id)
        return {"vaults_processed": len(vault_ids), "categories_refreshed": refreshed_count}


@dramatiq.actor(actor_name="refresh_daily_objectives", max_retries=3, min_backoff=3600000)
def refresh_daily_objectives():
    """Refresh daily objectives for all vaults.

    Returns:
        dict: Number of vaults processed and objectives assigned.
    """
    try:
        result = asyncio.run(_refresh_objectives())
    except Exception:
        logger.exception("Daily objectives refresh failed")
        raise
    else:
        logger.info(f"Daily objectives refresh completed: {result}")
        return result


@dramatiq.actor(actor_name="refresh_weekly_objectives", max_retries=3, min_backoff=3600000)
def refresh_weekly_objectives():
    """Refresh weekly objectives for all vaults.

    Returns:
        dict: Number of vaults processed and objectives assigned.
    """
    try:
        result = asyncio.run(_refresh_objectives())
    except Exception:
        logger.exception("Weekly objectives refresh failed")
        raise
    else:
        logger.info(f"Weekly objectives refresh completed: {result}")
        return result


async def _cleanup_old_records() -> dict:
    """Delete old incidents and notifications based on retention settings."""
    async with task_session() as session:
        incidents_deleted = await cleanup_service.cleanup_old_incidents(session)
        notifications_deleted = await cleanup_service.cleanup_old_notifications(session)
        return {
            "incidents_deleted": incidents_deleted,
            "notifications_deleted": notifications_deleted,
        }


@dramatiq.actor(actor_name="cleanup_old_records", max_retries=3, min_backoff=3600000)
def cleanup_old_records():
    """Clean up old incidents and notifications based on retention settings.

    Returns:
        dict: Counts of deleted incidents and notifications.
    """
    try:
        result = asyncio.run(_cleanup_old_records())
    except Exception:
        logger.exception("Cleanup of old records failed")
        raise
    else:
        logger.info(f"Cleanup completed: {result}")
        return result


# Periodiq schedule configuration
# These actors are scheduled to run periodically via Periodiq scheduler
# Command: periodiq app.core.dramatiq app.api.tasks

# Every minute (60 seconds)
game_tick.options["periodic"] = periodiq.cron("* * * * *")
incident_tick.options["periodic"] = periodiq.cron("*/2 * * * *")
check_quest_completion.options["periodic"] = periodiq.cron("* * * * *")

# Every 5 minutes
check_location_reclears.options["periodic"] = periodiq.cron("*/5 * * * *")

# Daily at midnight
check_permanent_deaths.options["periodic"] = periodiq.cron("0 0 * * *")
refresh_daily_objectives.options["periodic"] = periodiq.cron("0 0 * * *")
cleanup_old_records.options["periodic"] = periodiq.cron("0 0 * * *")

# Weekly on Monday at midnight
refresh_weekly_objectives.options["periodic"] = periodiq.cron("0 0 * * 1")
