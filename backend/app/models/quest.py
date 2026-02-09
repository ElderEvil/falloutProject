from enum import StrEnum
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.vault_quest import (
    VaultQuestCompletionLink,
)

if TYPE_CHECKING:
    from app.models.quest_requirement import QuestRequirement
    from app.models.quest_reward import QuestReward
    from app.models.vault import Vault


class QuestType(StrEnum):
    MAIN = "main"
    SIDE = "side"
    DAILY = "daily"
    EVENT = "event"
    REPEATABLE = "repeatable"


class QuestBase(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    short_description: str = Field(min_length=3, max_length=64)
    long_description: str = Field(min_length=3, max_length=255)
    requirements: str = Field(min_length=3, max_length=255)
    rewards: str = Field(min_length=3, max_length=255)
    quest_type: QuestType = Field(default=QuestType.SIDE, index=True)
    quest_category: str | None = Field(default=None, max_length=64, index=True)


class Quest(BaseUUIDModel, QuestBase, TimeStampMixin, table=True):
    vaults: list["Vault"] = Relationship(
        back_populates="quests",
        link_model=VaultQuestCompletionLink,
    )
    quest_requirements: list["QuestRequirement"] = Relationship(
        back_populates="quest",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    quest_rewards: list["QuestReward"] = Relationship(
        back_populates="quest",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
