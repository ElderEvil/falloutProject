from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models import LLMInteraction


class PromptBase(SQLModel):
    prompt_name: str = Field(min_length=3, max_length=32, index=True)
    description: str = Field(min_length=3, max_length=1000)
    prompt_template: str = Field()
    entity_id: UUID | None = Field(default=None, index=True)
    version: int = Field(default=1, ge=1, description="Immutable prompt version; new text = new row")
    is_active: bool = Field(default=True, index=True, description="Only one active row per prompt_name")

    def __str__(self):
        return f"{self.prompt_name}"


class Prompt(BaseUUIDModel, PromptBase, table=True):
    __table_args__ = (
        sa.UniqueConstraint("prompt_name", "version", name="uq_prompt_name_version"),
        # sqlite_where mirrors the PG partial index so SQLite tests enforce the same rule.
        sa.Index(
            "ix_prompt_active_name",
            "prompt_name",
            unique=True,
            postgresql_where=sa.text("is_active = true"),
            sqlite_where=sa.text("is_active = true"),
        ),
    )
    llm_interactions: list["LLMInteraction"] = Relationship(back_populates="prompt")
