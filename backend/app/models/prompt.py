from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel

from app.models.base import BaseUUIDModel
from app.schemas.common import AIModelType


class PromptBase(SQLModel):
    prompt_name: str = Field(min_length=3, max_length=32, index=True)
    description: str = Field(min_length=3, max_length=1000)
    prompt_template: str = Field(min_length=3, max_length=1000)
    entity_id: UUID | None = Field(default=None, index=True)
    ai_model_type: AIModelType = Field(default=AIModelType.CHATGPT)

    def generate_prompt(self, **kwargs) -> str:
        """
        Generate the full prompt by formatting the template with provided kwargs.
        """
        return self.prompt_template.format(**kwargs)

    def __str__(self):
        return f"{self.prompt_name}"


class Prompt(BaseUUIDModel, PromptBase, table=True):
    pass
