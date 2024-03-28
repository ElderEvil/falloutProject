from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class CommonFields(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    description: str = Field(min_length=3, max_length=255)
    completed: bool = False

    def __str__(self):
        return self.title


class QuestChainBase(CommonFields): ...


class QuestChain(BaseUUIDModel, QuestChainBase, TimeStampMixin, table=True):
    quests: list["Quest"] = Relationship(back_populates="chain")


class QuestBase(CommonFields): ...


class Quest(BaseUUIDModel, QuestBase, TimeStampMixin, table=True):
    chain_id: UUID4 = Field(foreign_key="questchain.id")
    chain: "QuestChain" = Relationship(back_populates="quests")
    steps: list["QuestStep"] = Relationship(back_populates="quest")


class QuestStepBase(CommonFields): ...


class QuestStep(BaseUUIDModel, QuestStepBase, TimeStampMixin, table=True):
    quest_id: UUID4 = Field(foreign_key="quest.id")
    quest: "Quest" = Relationship(back_populates="steps")
