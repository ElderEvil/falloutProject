from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.ai_settings import AISettings


class CRUDAISettings:
    """CRUD for the single-row AISettings table."""

    def __init__(self, model: type[AISettings]) -> None:
        self.model = model

    async def get_single(self, db_session: AsyncSession) -> AISettings | None:
        result = await db_session.execute(select(self.model).limit(1))
        return result.scalar_one_or_none()

    async def upsert(self, db_session: AsyncSession, obj_in: dict[str, Any]) -> AISettings:
        existing = await self.get_single(db_session)
        if existing is None:
            existing = self.model(**obj_in)
        else:
            for field, value in obj_in.items():
                setattr(existing, field, value)
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)
        return existing


ai_settings = CRUDAISettings(AISettings)
