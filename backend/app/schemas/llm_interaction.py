from datetime import datetime

from pydantic import UUID4

from app.models.llm_interaction import LLMInteractionBase


class LLMInteractionCreate(LLMInteractionBase):
    pass


class LLMInteractionRead(LLMInteractionBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
