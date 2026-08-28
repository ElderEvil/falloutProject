from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

async_engine = create_async_engine(
    str(settings.ASYNC_DATABASE_URI),
    echo=settings.ENVIRONMENT == "local",
    future=True,
    pool_size=settings.POOL_SIZE,
    max_overflow=64,
    # Force PostgreSQL connection to use UTC timezone
    # This ensures utc_now() values are correctly interpreted as UTC
    # Fixes 2-hour offset issue when system timezone differs from UTC
    connect_args={
        "server_settings": {"timezone": "UTC"},
    },
)

# Session maker for Celery tasks and other contexts
async_session_maker = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_maker() as session:
        yield session


@asynccontextmanager
async def task_session() -> AsyncGenerator[AsyncSession]:
    """Open a short-lived engine + session for background tick tasks.

    Background actors (arena/incident ticks) run in the dramatiq worker
    process, separate from the web app, so they get their own engine per run
    instead of sharing (and potentially poisoning) the app's pool. The engine
    is always disposed, even when the body raises.
    """
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
            yield session
    finally:
        await engine.dispose()
