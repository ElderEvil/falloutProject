from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.quest import QuestBase, QuestChainBase, QuestObjectiveBase
from app.utils.partial import optional


# Create schemas
class QuestChainCreate(QuestChainBase):
    pass


class QuestCreate(QuestBase):
    chain_id: UUID4 = Field(foreign_key="quest_chain.id")


class QuestObjectiveCreate(QuestObjectiveBase):
    quest_id: UUID4 = Field(foreign_key="quest.id")


# Read schemas
class QuestChainRead(QuestChainBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class QuestRead(QuestBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class QuestObjectiveRead(QuestObjectiveBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


# Update schemas
@optional()
class QuestChainUpdate(QuestChainBase):
    pass


@optional()
class QuestUpdate(QuestBase):
    pass


@optional()
class QuestObjectiveUpdate(QuestObjectiveBase):
    pass


# Nested read schemas
class QuestChainReadWithQuests(QuestChainRead):
    quests: list["QuestRead"] = []


class QuestReadWithQuestChain(QuestRead):
    chain: "QuestChainRead"


class QuestReadWithObjectives(QuestRead):
    objectives: list["QuestObjectiveRead"] = []


class QuestStepReadWithQuest(QuestObjectiveRead):
    quest: "QuestRead"


class QuestObjectiveJSON(SQLModel):
    title: str


class QuestJSON(SQLModel):
    quest_name: str
    long_description: str
    quest_objective: list[QuestObjectiveJSON]
    short_description: str
    requirements: str | list[str]
    rewards: str


class QuestChainJSON(SQLModel):
    title: str
    quests: list[QuestJSON]
