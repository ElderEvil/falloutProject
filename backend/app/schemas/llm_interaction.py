from datetime import datetime
from uuid import UUID

from app.models.llm_interaction import LLMInteractionBase


class LLMInteractionCreate(LLMInteractionBase):
    pass


class LLMInteractionRead(LLMInteractionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
