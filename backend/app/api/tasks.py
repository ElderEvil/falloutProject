import asyncio
import logging
import sys
import time

import dramatiq
import periodiq
from pydantic import UUID4

from app.services.cleanup_service import cleanup_service
from app.services.death_service import death_service
from app.services.game_loop import game_loop_service

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@dramatiq.actor(actor_name="create_task")
def create_task(task_time: int):
    time.sleep(task_time)
    return True


@dramatiq.actor(actor_name="game_tick", max_retries=3, min_backoff=60000)
def game_tick():
    """Main game tick - processes all active vaults. Scheduled every 60 seconds."""
    try:
        logger.info("Starting game tick")

        async def run_tick():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.services.objective_evaluators import evaluator_manager
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


@dramatiq.actor(actor_name="process_vault_tick", max_retries=3, min_backoff=30000)
def process_vault_tick(vault_id: str):
    """Process a single vault tick. Can be called manually or for catch-up processing."""
    try:
        logger.info(f"Processing vault tick for {vault_id}")

        async def run_vault_tick():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.services.objective_evaluators import evaluator_manager
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


@dramatiq.actor(actor_name="check_permanent_deaths", max_retries=3, min_backoff=3600000)
def check_permanent_deaths():
    """Check for dead dwellers past the revival window and mark them as permanently dead."""
    try:
        logger.info("Starting permanent death check")

        async def run_check():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)

            try:
                async with session_maker() as session:
                    count = await death_service.check_and_mark_permanent_deaths(session)
                    await session.commit()
                    return count
            finally:
                await engine.dispose()

        count = asyncio.run(run_check())
    except Exception:
        logger.exception("Permanent death check failed")
        raise
    else:
        logger.info(f"Permanent death check completed: {count} dwellers marked as permanently dead")
        return {"marked_permanently_dead": count}


@dramatiq.actor(actor_name="check_quest_completion", max_retries=3, min_backoff=300000)
def check_quest_completion():
    """Check for quests that have exceeded their duration and auto-complete them."""
    try:
        logger.info("Starting quest completion check")

        async def run_check():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.services.quest_service import quest_service

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)

            try:
                async with session_maker() as session:
                    count = await quest_service.check_and_complete_quests(session)
                    await session.commit()
                    return count
            finally:
                await engine.dispose()

        count = asyncio.run(run_check())
    except Exception:
        logger.exception("Quest completion check failed")
        raise
    else:
        logger.info(f"Quest completion check completed: {count} quests auto-completed")
        return {"quests_completed": count}


@dramatiq.actor(actor_name="refresh_daily_objectives", max_retries=3, min_backoff=3600000)
def refresh_daily_objectives():
    """Refresh daily objectives for all vaults."""
    try:
        logger.info("Starting daily objectives refresh")

        async def run_refresh():
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.models.vault import Vault
            from app.services.objective_assignment_service import ObjectiveAssignmentService

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)

            try:
                async with session_maker() as session:
                    result = await session.execute(select(Vault.id).where(Vault.deleted_at.is_(None)))
                    vault_ids = [row[0] for row in result.all()]

                    total_assigned = 0
                    for vault_id in vault_ids:
                        try:
                            service = ObjectiveAssignmentService(session)
                            assigned = await service.refresh_daily_objectives(vault_id)
                            total_assigned += len(assigned)
                        except Exception:
                            logger.exception(f"Failed to refresh daily objectives for vault {vault_id}")
                            continue

                    return {"vaults_processed": len(vault_ids), "objectives_assigned": total_assigned}
            finally:
                await engine.dispose()

        result = asyncio.run(run_refresh())
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
        logger.info("Starting weekly objectives refresh")

        async def run_refresh():
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.models.vault import Vault
            from app.services.objective_assignment_service import ObjectiveAssignmentService

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)

            try:
                async with session_maker() as session:
                    result = await session.execute(select(Vault.id).where(Vault.deleted_at.is_(None)))
                    vault_ids = [row[0] for row in result.all()]

                    total_assigned = 0
                    for vault_id in vault_ids:
                        try:
                            service = ObjectiveAssignmentService(session)
                            assigned = await service.refresh_weekly_objectives(vault_id)
                            total_assigned += len(assigned)
                        except Exception:
                            logger.exception(f"Failed to refresh weekly objectives for vault {vault_id}")
                            continue

                    return {"vaults_processed": len(vault_ids), "objectives_assigned": total_assigned}
            finally:
                await engine.dispose()

        result = asyncio.run(run_refresh())
    except Exception:
        logger.exception("Weekly objectives refresh failed")
        raise
    else:
        logger.info(f"Weekly objectives refresh completed: {result}")
        return result


@dramatiq.actor(actor_name="cleanup_old_records", max_retries=3, min_backoff=3600000)
def cleanup_old_records():
    """Clean up old incidents and notifications based on retention settings."""
    try:
        logger.info("Starting cleanup of old incidents and notifications")

        async def run_cleanup():
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
                connect_args={"server_settings": {"timezone": "UTC"}},
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)

            try:
                async with session_maker() as session:
                    incidents_deleted = await cleanup_service.cleanup_old_incidents(session)
                    notifications_deleted = await cleanup_service.cleanup_old_notifications(session)
                    return {
                        "incidents_deleted": incidents_deleted,
                        "notifications_deleted": notifications_deleted,
                    }
            finally:
                await engine.dispose()

        result = asyncio.run(run_cleanup())
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

# Daily at midnight
check_permanent_deaths.options["periodic"] = periodiq.cron("0 0 * * *")
refresh_daily_objectives.options["periodic"] = periodiq.cron("0 0 * * *")
cleanup_old_records.options["periodic"] = periodiq.cron("0 0 * * *")

# Weekly on Monday at midnight
refresh_weekly_objectives.options["periodic"] = periodiq.cron("0 0 * * 1")
