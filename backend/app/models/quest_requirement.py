from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.quest import Quest


class RequirementType(StrEnum):
    LEVEL = "level"
    ITEM = "item"
    ROOM = "room"
    DWELLER_COUNT = "dweller_count"
    QUEST_COMPLETED = "quest_completed"
    ATTACK = "attack"
    STAT = "stat"


class QuestRequirementBase(SQLModel):
    requirement_type: RequirementType = Field(index=True)
    requirement_data: dict[str, Any] = Field(default_factory=dict, sa_column=sa.Column(JSONB, nullable=False))
    is_mandatory: bool = Field(default=True)


class QuestRequirement(QuestRequirementBase, table=True):
    id: UUID4 = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    quest_id: UUID4 = Field(foreign_key="quest.id", index=True, ondelete="CASCADE")

    quest: "Quest" = Relationship(back_populates="quest_requirements")

    def __str__(self) -> str:
        label = str(self.requirement_type).replace("_", " ").title()
        details = ", ".join(f"{key.replace('_', ' ')}: {value}" for key, value in self.requirement_data.items())
        return f"{label} ({details})" if details else label
