from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

async_engine = create_async_engine(
    str(settings.ASYNC_DATABASE_URI),
    echo=settings.ENVIRONMENT == "local",
    future=True,
    pool_size=settings.POOL_SIZE,
    max_overflow=64,
    # Force PostgreSQL connection to use UTC timezone
    # This ensures datetime.utcnow() values are correctly interpreted as UTC
    # Fixes 2-hour offset issue when system timezone differs from UTC
    connect_args={
        "server_settings": {"timezone": "UTC"},
    },
)

# Session maker for Celery tasks and other contexts
async_session_maker = async_sessionmaker(
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

    Background actors (game/arena/incident ticks) run in the dramatiq worker
    process, separate from the web app, so they get their own engine per run
    instead of sharing (and potentially poisoning) the app's pool. The engine
    is always disposed, even when the body raises.

    The connection is pinned to UTC like the app engine: without it, naive-UTC
    timestamps are read back in the server's local zone.
    """
    engine = create_async_engine(
        str(settings.ASYNC_DATABASE_URI),
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args={"server_settings": {"timezone": "UTC"}},
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Objective event handlers open their own session when an event fires. Bind
    # the maker to this run so they use this fresh engine rather than the
    # module-global one, whose pooled connections belong to an earlier event
    # loop. Imported here: the evaluator package imports this module back.
    from app.services.progression.objectives.evaluators import current_session_maker, set_current_session_maker

    token = set_current_session_maker(session_maker)
    try:
        async with session_maker() as session:
            yield session
    finally:
        current_session_maker.reset(token)
        await engine.dispose()
