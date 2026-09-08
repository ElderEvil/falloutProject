from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.crud.base import CRUDBase
from app.models.prompt import Prompt
from app.schemas.prompt import PromptCreate, PromptUpdate


class CRUDPrompt(CRUDBase[Prompt, PromptCreate, PromptUpdate]):
    async def get_active(self, db_session: AsyncSession, name: str) -> Prompt | None:
        rows = await db_session.execute(
            select(Prompt).where(col(Prompt.prompt_name) == name, col(Prompt.is_active).is_(True))
        )
        return rows.scalars().first()

    async def get_versions_for_update(self, db_session: AsyncSession, name: str) -> list[Prompt]:
        rows = await db_session.execute(
            select(Prompt).where(col(Prompt.prompt_name) == name).order_by(col(Prompt.version).desc()).with_for_update()
        )
        return list(rows.scalars().all())

    async def replace_active(self, db_session: AsyncSession, active: Prompt, replacement: Prompt) -> None:
        active.is_active = False
        await db_session.flush()
        db_session.add(replacement)
        await db_session.flush()


prompt = CRUDPrompt(Prompt)
