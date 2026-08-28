"""Dramatiq task actors for scheduled game processing."""

import asyncio
import logging
import sys
import time
from typing import Final

import dramatiq
import periodiq
from pydantic import UUID4

import app.api.arena_tasks  # ruff: ignore[unused-import] - registers the arena_tick watchdog cron
import app.core.dramatiq  # ruff: ignore[unused-import] — ensures broker is configured when dramatiq CLI imports this module
from app.core.game_config import game_config
from app.db.session import task_session
from app.services.cleanup_service import cleanup_service
from app.services.death_service import death_service
from app.services.event_bus import event_bus
from app.services.game_loop import game_loop_service
from app.services.tick_chain import claim_tick_chain

logger = logging.getLogger(__name__)
INCIDENT_TICK_CHAIN_KEY: Final = "fallout:incident-tick:chain"

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


@dramatiq.actor(actor_name="game_tick", max_retries=3, min_backoff=60000)
def game_tick():
    """Main game tick - processes all active vaults. Scheduled every 60 seconds.

    Returns:
        dict: Game tick processing statistics.
    """
    try:
        logger.info("Starting game tick")

        async def run_tick():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.services.objective_evaluators import evaluator_manager, set_current_session_maker
            from app.services.objective_notifications import register_objective_event_handlers

            evaluator_manager.initialize()
            register_objective_event_handlers()

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)
            set_current_session_maker(session_maker)

            try:
                async with session_maker() as session:
                    return await game_loop_service.process_game_tick(session)
            finally:
                await engine.dispose()

        stats = asyncio.run(run_tick())
    except Exception:
        logger.exception("Game tick failed")
        raise
    else:
        logger.info(f"Game tick completed: {stats}")
        return stats
    finally:
        event_bus.clear_locks()


async def _run_incident_tick(chain_token: str | None) -> tuple[str | None, dict[str, int] | None]:
    """Claim the tick chain, then process one round of incident combat.

    Returns ``(next_chain_token, stats)``, or ``(None, None)`` when the chain
    lease was lost to another worker (the periodiq watchdog will re-seed it).
    A processing failure logs the error but still returns the claimed token,
    so the chain keeps self-scheduling instead of stalling until lease expiry.
    """
    from redis.asyncio import Redis

    from app.core.config import settings
    from app.services.incident_service import incident_service

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
    game tick) so incident combat gives live feedback. A Redis lease makes the
    periodiq cron below a low-frequency watchdog instead of a second tick chain.
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
            incident_tick.send_with_options(
                args=(next_chain_token,),
                delay=game_config.game_loop.incident_tick_seconds * 1000,
            )


@dramatiq.actor(actor_name="process_vault_tick", max_retries=3, min_backoff=30000)
def process_vault_tick(vault_id: str):
    """Process a single vault tick. Can be called manually or for catch-up processing.

    Args:
        vault_id: UUID string of the vault to process.

    Returns:
        dict: Vault tick processing result.
    """
    try:
        logger.info(f"Processing vault tick for {vault_id}")

        async def run_vault_tick():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.services.objective_evaluators import evaluator_manager, set_current_session_maker
            from app.services.objective_notifications import register_objective_event_handlers

            evaluator_manager.initialize()
            register_objective_event_handlers()

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)
            set_current_session_maker(session_maker)

            try:
                async with session_maker() as session:
                    return await game_loop_service.process_vault_tick(session, UUID4(vault_id))
            finally:
                await engine.dispose()

        result = asyncio.run(run_vault_tick())
    except Exception:
        logger.exception(f"Vault {vault_id} tick failed")
        raise
    else:
        logger.info(f"Vault {vault_id} tick completed")
        return result
    finally:
        event_bus.clear_locks()


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
    from app.services.quest_service import quest_service

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


async def _refresh_objectives(*, weekly: bool) -> dict:
    """Assign daily or weekly objectives to every non-deleted vault."""
    from sqlalchemy import select

    from app.models.vault import Vault
    from app.services.objective_assignment_service import ObjectiveAssignmentService

    async with task_session() as session:
        result = await session.execute(select(Vault.id).where(Vault.deleted_at.is_(None)))
        vault_ids = [row[0] for row in result.all()]

        total_assigned = 0
        for vault_id in vault_ids:
            try:
                service = ObjectiveAssignmentService(session)
                assigned = (
                    await service.refresh_daily_objectives(vault_id)
                    if not weekly
                    else await service.refresh_weekly_objectives(vault_id)
                )
                total_assigned += len(assigned)
            except Exception:
                logger.exception(f"Failed to refresh {'weekly' if weekly else 'daily'} objectives for vault {vault_id}")
                continue

        return {"vaults_processed": len(vault_ids), "objectives_assigned": total_assigned}


@dramatiq.actor(actor_name="refresh_daily_objectives", max_retries=3, min_backoff=3600000)
def refresh_daily_objectives():
    """Refresh daily objectives for all vaults.

    Returns:
        dict: Number of vaults processed and objectives assigned.
    """
    try:
        result = asyncio.run(_refresh_objectives(weekly=False))
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
        result = asyncio.run(_refresh_objectives(weekly=True))
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

# Daily at midnight
check_permanent_deaths.options["periodic"] = periodiq.cron("0 0 * * *")
refresh_daily_objectives.options["periodic"] = periodiq.cron("0 0 * * *")
cleanup_old_records.options["periodic"] = periodiq.cron("0 0 * * *")

# Weekly on Monday at midnight
refresh_weekly_objectives.options["periodic"] = periodiq.cron("0 0 * * 1")
