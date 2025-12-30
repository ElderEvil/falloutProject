from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlmodel import AutoString, Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.llm_interaction import LLMInteraction
    from app.models.user_profile import UserProfile
    from app.models.vault import Vault


class UserBase(SQLModel):
    username: str = Field(index=True, min_length=3, max_length=32, unique=True)
    email: EmailStr = Field(nullable=True, index=True, sa_column_kwargs={"unique": True}, sa_type=AutoString)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)


class User(BaseUUIDModel, UserBase, TimeStampMixin, table=True):
    hashed_password: str = Field(nullable=False)

    profile: "UserProfile" = Relationship(
        back_populates="user", cascade_delete=True, sa_relationship_kwargs={"uselist": False}
    )
    llm_interactions: list["LLMInteraction"] = Relationship(back_populates="user")
    vaults: list["Vault"] = Relationship(back_populates="user", cascade_delete=True)

    def __str__(self):
        return self.username
