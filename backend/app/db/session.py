from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
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
    # This ensures datetime.utcnow() values are correctly interpreted as UTC
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
