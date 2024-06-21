from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.vault_quest import (
    VaultQuestChainCompletionLink,
    VaultQuestCompletionLink,
    VaultQuestObjectiveCompletionLink,
)

if TYPE_CHECKING:
    from app.models.vault import Vault


class CommonFields(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)

    def __str__(self):
        return self.title


class QuestChainBase(CommonFields):
    pass


class QuestChain(BaseUUIDModel, QuestChainBase, table=True):
    quests: list["Quest"] = Relationship(back_populates="chain")
    vaults: list["Vault"] = Relationship(
        back_populates="quest_chains",
        link_model=VaultQuestChainCompletionLink,
    )


class QuestBase(CommonFields):
    long_description: str = Field(min_length=3, max_length=255)
    short_description: str = Field(min_length=3, max_length=64)
    requirements: str = Field(min_length=3, max_length=255)
    rewards: str = Field(min_length=3, max_length=255)


class Quest(BaseUUIDModel, QuestBase, TimeStampMixin, table=True):
    chain_id: UUID4 = Field(foreign_key="questchain.id")
    chain: "QuestChain" = Relationship(back_populates="quests")
    objectives: list["QuestObjective"] = Relationship(back_populates="quest")
    vaults: list["Vault"] = Relationship(
        back_populates="quests",
        link_model=VaultQuestCompletionLink,
    )


class QuestObjectiveBase(CommonFields):
    pass


class QuestObjective(BaseUUIDModel, QuestObjectiveBase, table=True):
    quest_id: UUID4 = Field(foreign_key="quest.id")
    quest: "Quest" = Relationship(back_populates="objectives")
    vaults: list["Vault"] = Relationship(
        back_populates="quest_objectives",
        link_model=VaultQuestObjectiveCompletionLink,
    )
