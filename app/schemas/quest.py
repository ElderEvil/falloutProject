from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.quest import QuestBase, QuestStepBase


class QuestCreate(QuestBase):
    pass


class QuestRead(QuestBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class QuestUpdate(SQLModel):
    title: str = None
    description: str = None
    completed: bool | None = False


class QuestStepCreate(QuestStepBase):
    quest_id: UUID4 = Field(foreign_key="quest.id")


class QuestStepUpdate(SQLModel):
    title: str | None = Field(index=True, min_length=3, max_length=64)
    description: str | None = Field(min_length=3, max_length=255)
    completed: bool | None = False


class QuestStepRead(QuestStepBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class QuestReadWithSteps(QuestRead):
    steps: list["QuestStepRead"] = []  # noqa: RUF012


class QuestStepReadWithQuest(QuestStepRead):
    quest: "QuestRead"
