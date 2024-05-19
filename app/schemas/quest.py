from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field

from app.models.quest import QuestBase, QuestStepBase
from app.utils.partial import optional


class QuestCreate(QuestBase):
    pass


class QuestRead(QuestBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


@optional()
class QuestUpdate(QuestBase):
    pass


class QuestStepCreate(QuestStepBase):
    quest_id: UUID4 = Field(foreign_key="quest.id")


@optional()
class QuestStepUpdate(QuestStepBase):
    pass


class QuestStepRead(QuestStepBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class QuestReadWithSteps(QuestRead):
    steps: list["QuestStepRead"] = []


class QuestStepReadWithQuest(QuestStepRead):
    quest: "QuestRead"
