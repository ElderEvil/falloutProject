from sqlmodel import SQLModel, Field, Relationship


class QuestBase(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    description: str = Field(min_length=3, max_length=255)
    completed: bool | None = False


class Quest(QuestBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    steps: list["QuestStep"] = Relationship(back_populates="quest")


class QuestCreate(QuestBase):
    pass


class QuestRead(QuestBase):
    id: int


class QuestUpdate(SQLModel):
    title: str = None
    description: str = None
    completed: bool | None = False


class QuestStepBase(SQLModel):
    title: str = Field(index=True, min_length=3, max_length=64)
    description: str = Field(min_length=3, max_length=255)
    order_number: int = 1
    completed: bool = False


class QuestStep(QuestStepBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    quest_id: int = Field(foreign_key="quest.id")
    quest: "Quest" = Relationship(back_populates="steps")


class QuestStepCreate(QuestStepBase):
    quest_id: int = Field(foreign_key="quest.id")


class QuestStepUpdate(SQLModel):
    title: str | None = Field(index=True, min_length=3, max_length=64)
    description: str | None = Field(min_length=3, max_length=255)
    completed: bool | None = False


class QuestStepRead(QuestStepBase):
    id: int


class QuestReadWithSteps(QuestRead):
    steps: list["QuestStepRead"] = []


class QuestStepReadWithQuest(QuestStepRead):
    quest: "QuestRead"
