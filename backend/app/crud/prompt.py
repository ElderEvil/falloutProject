from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.prompt import Prompt
from app.schemas.prompt import PromptCreate, PromptUpdate


class CRUDPrompt(CRUDBase[Prompt, PromptCreate, PromptUpdate]):
    async def get_prompt_by_name(self, db_session: AsyncSession, name: str) -> Prompt:
        query = await self.model.query.where(Prompt.prompt_name == name)
        response = await db_session.execute(query)
        return response.scalars().first()


prompt = CRUDPrompt(Prompt)
