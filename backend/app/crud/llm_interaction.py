from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, func, select

from app.crud.base import CRUDBase
from app.models.llm_interaction import LLMInteraction
from app.schemas.llm_interaction import LLMInteractionCreate


def estimate_token_count(text: str) -> int:
    """Estimate token count from text when the provider reports no usage.

    Roughly 4 characters per token; used for local providers (LM Studio,
    Ollama) that omit usage metadata so their chats still count toward the
    AI usage statistics and quota.
    """
    return max(1, len(text) // 4)


class CRUDLLMInteraction(CRUDBase[LLMInteraction, LLMInteractionCreate, None]):
    async def create(self, db_session: AsyncSession, obj_in: LLMInteractionCreate) -> LLMInteraction:
        if obj_in.prompt_tokens is None:
            obj_in.prompt_tokens = estimate_token_count(obj_in.parameters or "")
        if obj_in.completion_tokens is None:
            obj_in.completion_tokens = estimate_token_count(obj_in.response or "")
        if obj_in.total_tokens is None:
            obj_in.total_tokens = (obj_in.prompt_tokens or 0) + (obj_in.completion_tokens or 0)
        interaction = LLMInteraction.model_validate(obj_in)
        db_session.add(interaction)
        await db_session.flush()
        return interaction

    async def total_tokens_since(self, db_session: AsyncSession, user_id: UUID, since: datetime) -> int:
        result = await db_session.execute(
            select(func.sum(col(LLMInteraction.total_tokens))).where(
                col(LLMInteraction.user_id) == user_id, col(LLMInteraction.created_at) >= since
            )
        )
        return int(result.scalar_one() or 0)


llm_interaction = CRUDLLMInteraction(LLMInteraction)
