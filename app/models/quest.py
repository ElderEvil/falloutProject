from sqlmodel import Field, Relationship, SQLModel

from app.models.base import TimeStampMixin


class QuestBase(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    description: str = Field(min_length=3, max_length=255)
    completed: bool | None = False


class Quest(QuestBase, TimeStampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)

    steps: list["QuestStep"] = Relationship(back_populates="quest")


class QuestStepBase(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    description: str = Field(min_length=3, max_length=255)
    order_number: int = 1
    completed: bool = False


class QuestStep(QuestStepBase, TimeStampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)

    quest_id: int = Field(foreign_key="quest.id")
    quest: "Quest" = Relationship(back_populates="steps")
