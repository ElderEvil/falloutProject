import asyncio
import logging
import sys
import time

from pydantic import UUID4

from app.core.celery import celery_app
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

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)

            async with session_maker() as session:
                result = await game_loop_service.process_game_tick(session)
                await engine.dispose()
                return result

        stats = asyncio.run(run_tick())

        logger.info(f"Game tick completed: {stats}")  # noqa: G004
        return stats  # noqa: TRY300

    except Exception as e:
        logger.error(f"Game tick failed: {e}", exc_info=True)  # noqa: G004, G201
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds  # noqa: B904


@celery_app.task(name="process_vault_tick", bind=True)
def process_vault_tick_task(self, vault_id: str):
    """
    Process a single vault tick.
    Can be called manually or for catch-up processing.
    """
    try:
        logger.info(f"Processing vault tick for {vault_id}")  # noqa: G004

        async def run_vault_tick():
            # Create a new session maker in the current event loop context
            from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

            from app.core.config import settings

            engine = create_async_engine(
                str(settings.ASYNC_DATABASE_URI),
                echo=False,
                future=True,
                pool_pre_ping=True,
            )
            session_maker = async_sessionmaker(engine, expire_on_commit=False)

            async with session_maker() as session:
                result = await game_loop_service.process_vault_tick(session, UUID4(vault_id))
                await engine.dispose()
                return result

        result = asyncio.run(run_vault_tick())

        logger.info(f"Vault {vault_id} tick completed")  # noqa: G004
        return result  # noqa: TRY300

    except Exception as e:
        logger.error(f"Vault {vault_id} tick failed: {e}", exc_info=True)  # noqa: G004, G201
        raise self.retry(exc=e, countdown=30)  # noqa: B904
