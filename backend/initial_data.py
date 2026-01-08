"""
DEPRECATED: This file is no longer needed.

Initial data (admin user, test user, and test vault) is now seeded
automatically as part of the initial migration.

See: backend/app/alembic/versions/2026_01_08_1455-34f9ec11db72_initial.py

If you need to add more initial data in the future, either:
1. Add it to the initial migration, or
2. Create a new data migration using: alembic revision -m "add_more_data"
"""

import asyncio

from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.init_db import init_db
from app.db.session import async_engine

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_init_data() -> None:
    """DEPRECATED: Initial data is now in migrations."""
    print("WARNING: This script is deprecated. Initial data is seeded via migrations.")
    async with SessionLocal() as session:
        await init_db(session)


async def main() -> None:
    await create_init_data()


if __name__ == "__main__":
    asyncio.run(main())
