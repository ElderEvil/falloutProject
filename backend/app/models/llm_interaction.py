from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models.prompt import Prompt
    from app.models.user import User


class LLMInteractionBase(SQLModel):
    # ai_model_type: AIModelType = Field(default=AIModelType.CHATGPT)
    parameters: str | None
    response: str | None
    usage: str | None  # Legacy field - stores operation type (kept for backward compatibility)

    # Token tracking fields (for AI usage statistics)
    prompt_tokens: int | None = Field(default=None, ge=0, description="Number of tokens in the prompt")
    completion_tokens: int | None = Field(default=None, ge=0, description="Number of tokens in the completion")
    total_tokens: int | None = Field(default=None, ge=0, description="Total tokens used (prompt + completion)")

    prompt_id: UUID | None = Field(default=None, foreign_key="prompt.id")
    user_id: UUID | None = Field(default=None, foreign_key="user.id", index=True)


class LLMInteraction(BaseUUIDModel, LLMInteractionBase, table=True):
    created_at: datetime | None = Field(default_factory=lambda: datetime.utcnow())  # noqa: PLW0108

    prompt: "Prompt" = Relationship(back_populates="llm_interactions")
    user: "User" = Relationship(back_populates="llm_interactions")

    def __str__(self):
        return f"{self.usage}"
