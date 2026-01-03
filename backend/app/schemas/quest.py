from pydantic import UUID4, Field
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


class QuestObjectiveJSON(SQLModel):
    """Schema for quest objectives in JSON files."""

    title: str


class QuestJSON(SQLModel):
    """Schema for individual quests in JSON files with field aliases for JSON compatibility."""

    quest_name: str = Field(alias="Quest name")
    long_description: str = Field(alias="Long description")
    short_description: str = Field(alias="Short description")
    requirements: str | list[str] = Field(alias="Requirements")
    rewards: str = Field(alias="Rewards")
    # Quest objective can be a string or list of objects in the JSON
    quest_objective: str | list[QuestObjectiveJSON] | None = Field(default=None, alias="Quest objective")


class QuestChainJSON(SQLModel):
    """Schema for quest chains (collection of related quests)."""

    title: str
    quests: list[QuestJSON]
