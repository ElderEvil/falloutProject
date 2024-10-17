from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.vault_quest import (
    VaultQuestCompletionLink,
)

if TYPE_CHECKING:
    from app.models.vault import Vault


class QuestBase(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    short_description: str = Field(min_length=3, max_length=64)
    long_description: str = Field(min_length=3, max_length=255)
    requirements: str = Field(min_length=3, max_length=255)
    rewards: str = Field(min_length=3, max_length=255)


class Quest(BaseUUIDModel, QuestBase, TimeStampMixin, table=True):
    vaults: list["Vault"] = Relationship(
        back_populates="quests",
        link_model=VaultQuestCompletionLink,
    )
