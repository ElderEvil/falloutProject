from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimeStampMixin, BaseUUIDModel


class QuestBase(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    description: str = Field(min_length=3, max_length=255)
    completed: bool | None = False


class Quest(BaseUUIDModel, QuestBase, TimeStampMixin, table=True):
    steps: list["QuestStep"] = Relationship(back_populates="quest")


class QuestStepBase(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    description: str = Field(min_length=3, max_length=255)
    order_number: int = 1
    completed: bool = False


class QuestStep(BaseUUIDModel, QuestStepBase, TimeStampMixin, table=True):
    quest_id: UUID4 = Field(foreign_key="quest.id")
    quest: "Quest" = Relationship(back_populates="steps")
