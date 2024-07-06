from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlmodel import AutoString, Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.vault import Vault


class UserBase(SQLModel):
    username: str = Field(index=True, min_length=3, max_length=32, unique=True)
    email: EmailStr = Field(nullable=True, index=True, sa_column_kwargs={"unique": True}, sa_type=AutoString)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)


class User(BaseUUIDModel, UserBase, TimeStampMixin, table=True):
    hashed_password: str = Field(nullable=False)

    vaults: list["Vault"] = Relationship(back_populates="user", sa_relationship_kwargs={"cascade": "all, delete"})

    def __str__(self):
        return self.username
