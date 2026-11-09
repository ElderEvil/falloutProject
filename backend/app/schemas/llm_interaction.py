from uuid import UUID

from app.models.llm_interaction import LLMInteractionBase
from app.utils.serialize_types import UTCDateTimeJSON


class LLMInteractionCreate(LLMInteractionBase):
    pass


class LLMInteractionRead(LLMInteractionBase):
    id: UUID
    created_at: UTCDateTimeJSON
    updated_at: UTCDateTimeJSON
