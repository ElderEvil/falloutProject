import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.ai_settings import AISettings

# Single-row table: all settings live in one well-known row so concurrent
# upserts cannot create duplicates. A fixed PK makes the upsert effectively
# atomic (the INSERT is idempotent on conflict). The value is a valid UUID v4
# (version nibble 4, variant nibble 8) so it passes the UUID4 schema field.
SINGLETON_ROW_ID = uuid.UUID("f1a2b3c4-d5e6-4000-8000-000000000001")


class CRUDAISettings:
    """CRUD for the single-row AISettings table."""

    def __init__(self, model: type[AISettings]) -> None:
        self.model = model

    async def get_single(self, db_session: AsyncSession) -> AISettings | None:
        result = await db_session.execute(select(self.model).where(self.model.id == SINGLETON_ROW_ID))
        row = result.scalar_one_or_none()
        if row is not None:
            return row
        # Fallback: adopt any pre-existing row (e.g. created before the fixed PK).
        result = await db_session.execute(select(self.model).limit(1))
        return result.scalar_one_or_none()

    async def upsert(self, db_session: AsyncSession, obj_in: dict[str, Any]) -> AISettings:
        existing = await self.get_single(db_session)
        if existing is None:
            try:
                existing = self.model(id=SINGLETON_ROW_ID, **obj_in)
                db_session.add(existing)
                await db_session.commit()
            except IntegrityError:
                # Another request created the singleton row concurrently.
                await db_session.rollback()
                existing = await self.get_single(db_session)
                if existing is None:
                    raise
        for field, value in obj_in.items():
            setattr(existing, field, value)
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)
        return existing


ai_settings = CRUDAISettings(AISettings)
