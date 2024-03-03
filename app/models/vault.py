from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.user import User


class VaultBase(SQLModel):
    name: int = Field(index=True, gt=0, lt=1_000)
    bottle_caps: int = Field(default=1000, ge=0, lt=1_000_000)
    happiness: int = Field(default=50, ge=0, le=100)

    def __str__(self):
        return f"Vault {self.name:03}"


class Vault(BaseUUIDModel, VaultBase, TimeStampMixin, table=True):
    user_id: UUID4 = Field(default=None, foreign_key="user.id")

    user: "User" = Relationship(back_populates="vaults")
