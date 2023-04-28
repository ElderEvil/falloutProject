from sqlmodel import SQLModel, Field

from app.models.quest import QuestBase, QuestStepBase


class QuestCreate(QuestBase):
    pass


class QuestRead(QuestBase):
    id: int


class QuestUpdate(SQLModel):
    title: str = None
    description: str = None
    completed: bool | None = False


class QuestStepCreate(QuestStepBase):
    quest_id: int = Field(foreign_key="quest.id")


class QuestStepUpdate(SQLModel):
    title: str | None = Field(index=True, min_length=3, max_length=64)
    description: str | None = Field(min_length=3, max_length=255)
    completed: bool | None = False


class QuestStepRead(QuestStepBase):
    id: int


class QuestReadWithSteps(QuestRead):
    steps: list["QuestStepRead"] = []


class QuestStepReadWithQuest(QuestStepRead):
    quest: "QuestRead"
