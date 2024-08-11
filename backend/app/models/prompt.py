from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import Field
from sqlmodel import Relationship, SQLModel

from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models import LLMInteraction


class PromptBase(SQLModel):
    # ai_model_type: AIModelType = Field(default=AIModelType.CHATGPT)
    prompt_name: str = Field(min_length=3, max_length=32, index=True)
    description: str = Field(min_length=3, max_length=1000)
    prompt_template: str = Field()
    entity_id: UUID | None = Field(default=None, index=True)

    def generate_prompt(self, **kwargs) -> str:
        """
        Generate the full prompt by formatting the template with provided kwargs.
        """
        return self.prompt_template.format(**kwargs)

    def __str__(self):
        return f"{self.prompt_name}"


class Prompt(BaseUUIDModel, PromptBase, table=True):
    llm_interactions: list["LLMInteraction"] = Relationship(back_populates="prompt")
