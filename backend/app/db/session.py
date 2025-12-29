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
