"""Dramatiq task actors for scheduled game processing."""

import asyncio
import logging
import os
import sys
import time
from contextlib import suppress
from typing import Final
from uuid import UUID, uuid4

import dramatiq
import periodiq
from dramatiq.middleware import CurrentMessage
from redis.asyncio import Redis

import app.api.arena_tasks  # ruff: ignore[unused-import] - registers the arena_tick watchdog cron
import app.api.world_event_tasks  # ruff: ignore[unused-import] - registers the advance_world_event cron
import app.core.dramatiq  # ruff: ignore[unused-import] — ensures broker is configured when dramatiq CLI imports this module
from app.core.async_runtime import run_async
from app.core.config import settings
from app.core.event_bus import event_bus
from app.core.game_config import game_config
from app.core.tick_chain import claim_tick_chain
from app.core.tick_profiling import (
    TickProfile,
    current_profile,
    profile_key,
    reset_current_profile,
    set_current_profile,
    tick_phase,
)
from app.db.session import task_session
from app.models.vault import Vault
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
VAULT_TICK_LOCK_RENEW_INTERVAL_SECONDS: Final = 15
VAULT_TICK_LOCK_RELEASE_SCRIPT: Final = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""
VAULT_TICK_LOCK_REFRESH_SCRIPT: Final = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


class VaultTickLeaseLost(RuntimeError):
    """Raised when a vault tick's Redis lease can no longer be renewed."""


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@dramatiq.actor(actor_name="create_task")
def create_task(task_time: int):
    """Test actor: sleep task_time seconds, then return True."""
    time.sleep(task_time)
    return True


async def _dispatch_game_tick(tick_id: str) -> dict[str, int | float]:
    async with task_session() as session:
        vault_ids = await game_loop_service.get_active_vault_ids(session)
    for vault_id in vault_ids:
        process_vault_tick.send(str(vault_id), tick_id)
    return {"vaults_dispatched": len(vault_ids)}


@dramatiq.actor(actor_name="game_tick", max_retries=3, min_backoff=60000)
def game_tick():
    """Dispatch one vault tick per active vault. Scheduled every 60 seconds."""
    start = time.perf_counter()
    message = CurrentMessage.get_current_message()
    # Celery message id fallback; not a database row.
    tick_id = message.message_id if message is not None else uuid4().hex
    try:
        logger.info("Dispatching game tick")
        stats: dict[str, int | float] = run_async(_dispatch_game_tick(tick_id))
    except Exception:
        logger.exception("Game tick dispatch failed")
        raise
    stats["dispatch_time"] = round(time.perf_counter() - start, 3)
    logger.info("Game tick dispatched: %s tick_id=%s", stats, tick_id)
    return stats


async def _run_incident_tick(chain_token: str | None) -> tuple[str | None, dict[str, int] | None]:
    """Claim the chain, process one incident round; return (next_token, stats).

    (None, None) when the lease is lost (the periodiq watchdog re-seeds it).
    Failures still return the claimed token so the chain keeps self-scheduling.
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
    """Fast incident-combat tick; self-reschedules every incident_tick_seconds.

    A Redis lease plus short-TTL heartbeat lets the periodiq cron below watchdog
    the chain: re-seed when dead, take over once the heartbeat expires.
    """
    next_chain_token = None
    try:
        next_chain_token, stats = run_async(_run_incident_tick(chain_token))
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
    # Opaque lock-ownership token; ordering is irrelevant.
    token = uuid4().hex
    acquired = await redis.set(f"{VAULT_TICK_LOCK_PREFIX}{vault_id}", token, nx=True, ex=VAULT_TICK_LOCK_TTL_SECONDS)
    return token if acquired else None


async def _refresh_vault_tick_lock(redis: Redis, vault_id: str, token: str, ttl: int) -> bool:
    refreshed = await redis.eval(
        VAULT_TICK_LOCK_REFRESH_SCRIPT, 1, f"{VAULT_TICK_LOCK_PREFIX}{vault_id}", token, str(ttl)
    )
    return bool(refreshed)


async def _release_vault_tick_lock(redis: Redis, vault_id: str, token: str) -> None:
    await redis.eval(VAULT_TICK_LOCK_RELEASE_SCRIPT, 1, f"{VAULT_TICK_LOCK_PREFIX}{vault_id}", token)


async def _renew_vault_tick_lock(redis: Redis, vault_id: str, token: str) -> None:
    while True:
        await asyncio.sleep(VAULT_TICK_LOCK_RENEW_INTERVAL_SECONDS)
        if not await _refresh_vault_tick_lock(redis, vault_id, token, VAULT_TICK_LOCK_TTL_SECONDS):
            raise VaultTickLeaseLost(vault_id)


async def _run_vault_tick(vault_id: str, tick_id: str | None) -> VaultTickResult:
    from app.services.progression.objectives.evaluators import evaluator_manager
    from app.services.progression.objectives.notifications import register_objective_event_handlers

    with tick_phase("actor_setup"):
        evaluator_manager.initialize()
        register_objective_event_handlers()

    profile = current_profile()
    engine_started = time.perf_counter()
    async with task_session() as session:
        if profile is not None:
            await session.connection()
            profile.add("engine_session", (time.perf_counter() - engine_started) * 1000)
        with tick_phase("service"):
            return await game_loop_service.process_vault_tick(session, UUID(vault_id), tick_id)


async def _process_vault_tick_async(vault_id: str, redis: Redis, tick_id: str | None = None) -> VaultTickResult:
    loop_id = id(asyncio.get_running_loop())
    with tick_phase("lock_acquire"):
        token = await _acquire_vault_tick_lock(redis, vault_id)
    if token is None:
        return {"status": "skipped"}

    renewal: asyncio.Task[None] | None = None
    try:
        renewal = asyncio.create_task(_renew_vault_tick_lock(redis, vault_id, token))
        tick = asyncio.create_task(_run_vault_tick(vault_id, tick_id))
        done, _ = await asyncio.wait({tick, renewal}, return_when=asyncio.FIRST_COMPLETED)
        if tick not in done:
            tick.cancel()
            with suppress(asyncio.CancelledError):
                await tick
            renewal.result()
            raise AssertionError("vault tick lease renewal returned unexpectedly")

        return tick.result()
    except ResourceNotFoundException as exc:
        if exc.model is not Vault:
            raise
        logger.warning(f"Vault {vault_id} no longer exists; skipping tick")
        return {"status": "missing"}
    finally:
        if renewal is not None:
            renewal.cancel()
            with suppress(asyncio.CancelledError, VaultTickLeaseLost):
                await renewal
        await _release_vault_tick_lock(redis, vault_id, token)
        event_bus.clear_locks(loop_id)


@dramatiq.actor(actor_name="process_vault_tick", max_retries=3, min_backoff=30000)
def process_vault_tick(vault_id: str, tick_id: str | None = None, enqueued_at: float | None = None) -> None:
    """Process one vault tick under a per-vault Redis lease.

    Deliberately returns None: a payload would reach Dramatiq's Results
    middleware, which warns on every tick.
    """
    start = time.perf_counter()
    profile = None
    if os.getenv("TICK_PROFILE") == "1":
        if enqueued_at is None:
            message = CurrentMessage.get_current_message()
            enqueued_at = message.message_timestamp / 1000 if message is not None else None
        profile = TickProfile(
            vault_key=profile_key(vault_id),
            dispatch_key=profile_key(tick_id) if tick_id else "",
            enqueued_at=enqueued_at,
        )
    profile_token = set_current_profile(profile)

    async def run_vault_tick():
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            return await _process_vault_tick_async(vault_id, redis, tick_id)
        finally:
            await redis.aclose()

    try:
        result = run_async(run_vault_tick())
    except Exception:
        logger.exception(f"Vault {vault_id} tick failed")
        raise
    finally:
        if profile is not None:
            profile.finish()
            logger.info("Vault tick profile: %s", profile.summary())
        reset_current_profile(profile_token)
    if result.get("status") in {"skipped", "missing", "duplicate"}:
        logger.info(f"Vault {vault_id} tick {result['status']}")
    else:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Vault {vault_id} tick completed in {elapsed_ms:.1f}ms")


async def _check_permanent_deaths() -> int:
    """Mark dead dwellers past the revival window as permanently dead."""
    async with task_session() as session:
        count = await death_service.check_and_mark_permanent_deaths(session)
        await session.commit()
        return count


@dramatiq.actor(actor_name="check_permanent_deaths", max_retries=3, min_backoff=3600000)
def check_permanent_deaths():
    """Mark dead dwellers past the revival window permanently dead; return the count."""
    try:
        count = run_async(_check_permanent_deaths())
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
    """Auto-complete quests past their duration; return the count."""
    try:
        count = run_async(_check_quest_completion())
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
    """Sweep map points whose reclear window elapsed and notify owners; return the count."""
    try:
        count = run_async(_check_location_reclears())
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
        failed: list[str] = []
        for vault_id in vault_ids:
            try:
                refreshed_count += len(await ensure_current_objectives(session, vault_id))
            except Exception:
                await recover_session(session)
                logger.exception("Objective refresh failed for vault %s", vault_id)
                failed.append(str(vault_id))
        if failed:
            # Retryable: the period stamps make re-refreshing already-current vaults a no-op.
            raise RuntimeError(f"Objective refresh failed for vaults: {', '.join(failed)}")
        return {"vaults_processed": len(vault_ids), "categories_refreshed": refreshed_count}


@dramatiq.actor(actor_name="refresh_daily_objectives", max_retries=3, min_backoff=3600000)
def refresh_daily_objectives():
    """Refresh daily objectives for all vaults."""
    try:
        result = run_async(_refresh_objectives())
    except Exception:
        logger.exception("Daily objectives refresh failed")
        raise
    else:
        logger.info(f"Daily objectives refresh completed: {result}")
        return result


@dramatiq.actor(actor_name="refresh_weekly_objectives", max_retries=3, min_backoff=3600000)
def refresh_weekly_objectives():
    """Refresh weekly objectives for all vaults."""
    try:
        result = run_async(_refresh_objectives())
    except Exception:
        logger.exception("Weekly objectives refresh failed")
        raise
    else:
        logger.info(f"Weekly objectives refresh completed: {result}")
        return result


async def _refresh_quest_rotation() -> dict:
    """Rotate due daily/weekly quests for every non-deleted vault through the shared UTC policy."""
    from app.crud.vault import vault as vault_crud
    from app.services.progression.quests.rotation import ensure_current_quest_rotation

    async with task_session() as session:
        vault_ids = await vault_crud.get_non_deleted_ids(session)
        offered_count = 0
        failed: list[str] = []
        for vault_id in vault_ids:
            try:
                offered_count += await ensure_current_quest_rotation(session, vault_id)
            except Exception:
                await recover_session(session)
                logger.exception("Quest rotation failed for vault %s", vault_id)
                failed.append(str(vault_id))
        if failed:
            # Retryable: period stamps make re-rotation idempotent.
            raise RuntimeError(f"Quest rotation failed for vaults: {', '.join(failed)}")
        return {"vaults_processed": len(vault_ids), "quests_offered": offered_count}


@dramatiq.actor(actor_name="refresh_quest_rotation", max_retries=3, min_backoff=3600000)
def refresh_quest_rotation():
    """Rotate daily and weekly quests for all vaults."""
    result = run_async(_refresh_quest_rotation())
    logger.info("Quest rotation completed: %s", result)
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
    """Delete old incidents and notifications per retention settings."""
    try:
        result = run_async(_cleanup_old_records())
    except Exception:
        logger.exception("Cleanup of old records failed")
        raise
    else:
        logger.info(f"Cleanup completed: {result}")
        return result


# Periodiq schedule; run with: periodiq app.core.dramatiq app.api.tasks

game_tick.options["periodic"] = periodiq.cron("* * * * *")
incident_tick.options["periodic"] = periodiq.cron("*/2 * * * *")
check_quest_completion.options["periodic"] = periodiq.cron("* * * * *")

check_location_reclears.options["periodic"] = periodiq.cron("*/5 * * * *")

check_permanent_deaths.options["periodic"] = periodiq.cron("0 0 * * *")
refresh_daily_objectives.options["periodic"] = periodiq.cron("0 0 * * *")
refresh_quest_rotation.options["periodic"] = periodiq.cron("0 0 * * *")
cleanup_old_records.options["periodic"] = periodiq.cron("0 0 * * *")

refresh_weekly_objectives.options["periodic"] = periodiq.cron("0 0 * * 1")
