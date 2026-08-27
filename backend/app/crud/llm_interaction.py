from sqlmodel.ext.asyncio.session import AsyncSession

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
        return await super().create(db_session, obj_in=obj_in)


llm_interaction = CRUDLLMInteraction(LLMInteraction)
