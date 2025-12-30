from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserProfileBase(SQLModel):
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=255)
    preferences: dict | None = Field(default=None, sa_column=sa.Column(JSONB))

    # Statistics (calculated, not user-editable)
    total_dwellers_created: int = Field(default=0, ge=0)
    total_caps_earned: int = Field(default=0, ge=0)
    total_explorations: int = Field(default=0, ge=0)
    total_rooms_built: int = Field(default=0, ge=0)


class UserProfile(BaseUUIDModel, UserProfileBase, TimeStampMixin, table=True):
    user_id: UUID4 = Field(foreign_key="user.id", unique=True, index=True)
    user: "User" = Relationship(back_populates="profile")

    def __str__(self):
        return f"Profile of User {self.user_id}"
