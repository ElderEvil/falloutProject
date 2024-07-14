from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field

from app.models.base import BaseUUIDModel


class LLMInteraction(BaseUUIDModel, table=True):
    created_at: datetime | None = Field(default_factory=datetime.utcnow)
    model: str
    prompt: str
    parameters: str | None = Field(default=None)
    response: str | None = Field(default=None)
    usage: str | None = Field(default=None)

    user_id: UUID4 | None = Field(default=None)
