from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings

async_engine = create_async_engine(
    str(settings.ASYNC_DATABASE_URI),
    echo=True,
    future=True,
    pool_size=settings.POOL_SIZE,
    max_overflow=64,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session
