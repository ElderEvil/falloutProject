import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from threading import Lock
from weakref import WeakKeyDictionary

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
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


_task_engines: WeakKeyDictionary[asyncio.AbstractEventLoop, AsyncEngine] = WeakKeyDictionary()
_task_engines_lock = Lock()


def _task_engine() -> AsyncEngine:
    """Return the task engine bound to the current event loop.

    Dramatiq worker threads keep one event loop for their lifetime (see
    ``app.core.async_runtime.run_async``), so caching per loop lets consecutive
    ticks reuse asyncpg connections and their type introspection instead of
    rebuilding an engine for every message. Loops never share an engine.
    """
    loop = asyncio.get_running_loop()
    with _task_engines_lock:
        engine = _task_engines.get(loop)
    if engine is None:
        engine = create_async_engine(
            str(settings.ASYNC_DATABASE_URI),
            echo=False,
            future=True,
            pool_pre_ping=True,
            # One tick session plus one nested objective-handler session; other
            # worker loops must not multiply the default 5 + 10 pool.
            pool_size=2,
            max_overflow=0,
            connect_args={"server_settings": {"timezone": "UTC"}},
        )
        with _task_engines_lock:
            _task_engines[loop] = engine
    return engine


@asynccontextmanager
async def task_session_maker() -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    """Yield the loop-scoped session maker for background tick tasks.

    Background actors (game/arena/incident ticks) run in the dramatiq worker
    process, separate from the web app, so they must not share the app's pool.
    They do reuse one pool per worker event loop: ``run_async`` keeps the loop
    alive across messages, and this engine is cached against that loop.

    The connection is pinned to UTC like the app engine: without it, naive-UTC
    timestamps are read back in the server's local zone.
    """
    session_maker = async_sessionmaker(_task_engine(), class_=AsyncSession, expire_on_commit=False)

    # Objective event handlers open their own session when an event fires. Bind
    # the maker to this run so they use the loop-scoped task pool rather than
    # the module-global one, whose pooled connections belong to the web loop.
    # Imported here: the evaluator package imports this module back.
    from app.services.progression.objectives.evaluators import current_session_maker, set_current_session_maker

    token = set_current_session_maker(session_maker)
    try:
        yield session_maker
    finally:
        current_session_maker.reset(token)


@asynccontextmanager
async def task_session() -> AsyncGenerator[AsyncSession]:
    """Open one session from a run-scoped engine; see ``task_session_maker``."""
    async with task_session_maker() as session_maker, session_maker() as session:
        yield session
