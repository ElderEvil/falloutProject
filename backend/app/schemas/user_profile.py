from datetime import datetime

from pydantic import UUID4
from sqlmodel import SQLModel

from app.models.user_profile import UserProfileBase
from app.utils.partial import optional


class ProfileRead(UserProfileBase):
    id: UUID4
    user_id: UUID4
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(SQLModel):
    bio: str | None = None
    avatar_url: str | None = None
    preferences: dict | None = None


@optional()
class ProfileUpdateStatistics(SQLModel):
    """For internal use only - updating statistics."""

    total_dwellers_created: int | None = None
    total_caps_earned: int | None = None
    total_explorations: int | None = None
    total_rooms_built: int | None = None
