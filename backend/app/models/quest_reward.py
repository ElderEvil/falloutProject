from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.quest import Quest


class RewardType(StrEnum):
    CAPS = "caps"
    ITEM = "item"
    DWELLER = "dweller"
    RESOURCE = "resource"
    EXPERIENCE = "experience"
    STIMPAK = "stimpak"
    RADAWAY = "radaway"
    LUNCHBOX = "lunchbox"


class QuestRewardBase(SQLModel):
    reward_type: RewardType = Field(index=True)
    reward_data: dict[str, Any] = Field(default_factory=dict, sa_column=sa.Column(JSONB, nullable=False))
    reward_chance: float = Field(default=1.0, ge=0.0, le=1.0)


class QuestReward(QuestRewardBase, table=True):
    id: UUID4 = Field(default_factory=uuid4, primary_key=True, index=True, nullable=False)
    quest_id: UUID4 = Field(foreign_key="quest.id", index=True, ondelete="CASCADE")

    quest: "Quest" = Relationship(back_populates="quest_rewards")
