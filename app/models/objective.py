from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models.vault import Vault


class ObjectiveBase(SQLModel):
    challenge: str = Field(min_length=3, max_length=32, index=True)
    reward: str = Field(min_length=3, max_length=32)

    def __str__(self):
        return f"{self.challenge}"


class Objective(BaseUUIDModel, ObjectiveBase, table=True):
    vaults: list["Vault"] = Relationship(back_populates="objectives")
