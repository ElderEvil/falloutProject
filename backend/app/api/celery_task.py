import asyncio
import logging
import sys
import time

from pydantic import UUID4

from app.core.celery import celery_app
from app.services.death_service import death_service
from app.services.game_loop import game_loop_service

logger = logging.getLogger(__name__)

# Fix for Windows asyncio + asyncpg issue
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@celery_app.task(name="create_task1")
def create_task(task_time: int):
    time.sleep(task_time)
    return True


@celery_app.task(bind=True, max_retries=3)
def generate_dweller_attributes():  # TODO: Implement generate with AI
    pass


@celery_app.task(name="game_tick", bind=True)
def game_tick_task(self):
    """
    Main game tick task - processes all active vaults.
    Scheduled to run every 60 seconds via Celery Beat.
    """
    try:
        logger.info("Starting game tick")

        async def run_tick():
            # Create a new session maker in the current event loop context
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.services.objective_evaluators import evaluator_manager
            from app.services.objective_notifications import register_objective_event_handlers

            # Initialize objective evaluators (Celery runs in separate process)
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
    except Exception as e:
        logger.exception("Game tick failed")
        raise self.retry(exc=e, countdown=60) from e
    else:
        logger.info(f"Game tick completed: {stats}")
        return stats


@celery_app.task(name="process_vault_tick", bind=True)
def process_vault_tick_task(self, vault_id: str):
    """
    Process a single vault tick.
    Can be called manually or for catch-up processing.
    """
    try:
        logger.info(f"Processing vault tick for {vault_id}")

        async def run_vault_tick():
            # Create a new session maker in the current event loop context
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings
            from app.services.objective_evaluators import evaluator_manager
            from app.services.objective_notifications import register_objective_event_handlers

            # Initialize objective evaluators (Celery runs in separate process)
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
    except Exception as e:
        logger.exception(f"Vault {vault_id} tick failed")
        raise self.retry(exc=e, countdown=30) from e
    else:
        logger.info(f"Vault {vault_id} tick completed")
        return result


@celery_app.task(name="check_permanent_deaths", bind=True)
def check_permanent_deaths_task(self):
    """
    Check for dead dwellers past the revival window and mark them as permanently dead.
    Scheduled to run daily via Celery Beat.
    """
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
    except Exception as e:
        logger.exception("Permanent death check failed")
        raise self.retry(exc=e, countdown=3600) from e  # Retry in 1 hour
    else:
        logger.info(f"Permanent death check completed: {count} dwellers marked as permanently dead")
        return {"marked_permanently_dead": count}


@celery_app.task(name="check_quest_completion", bind=True)
def check_quest_completion_task(self):
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
    except Exception as e:
        logger.exception("Quest completion check failed")
        raise self.retry(exc=e, countdown=300) from e
    else:
        logger.info(f"Quest completion check completed: {count} quests auto-completed")
        return {"quests_completed": count}


@celery_app.task(name="refresh_daily_objectives", bind=True)
def refresh_daily_objectives_task(self):
    """Refresh daily objectives for all vaults. Scheduled to run daily via Celery Beat."""
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
    except Exception as e:
        logger.exception("Daily objectives refresh failed")
        raise self.retry(exc=e, countdown=3600) from e
    else:
        logger.info(f"Daily objectives refresh completed: {result}")
        return result


@celery_app.task(name="refresh_weekly_objectives", bind=True)
def refresh_weekly_objectives_task(self):
    """Refresh weekly objectives for all vaults. Scheduled to run weekly via Celery Beat."""
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
    except Exception as e:
        logger.exception("Weekly objectives refresh failed")
        raise self.retry(exc=e, countdown=3600) from e
    else:
        logger.info(f"Weekly objectives refresh completed: {result}")
        return result
