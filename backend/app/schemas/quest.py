from pydantic import UUID4
from sqlmodel import SQLModel

from app.models.quest import QuestBase
from app.utils.partial import optional


class QuestCreate(QuestBase):
    pass


class QuestRead(QuestBase):
    id: UUID4


class QuestReadShort(SQLModel):
    id: UUID4
    title: str
    short_description: str


@optional()
class QuestUpdate(QuestBase):
    pass


class QuestJSON(SQLModel):
    quest_name: str
    long_description: str
    short_description: str
    requirements: str | list[str]
    rewards: str
