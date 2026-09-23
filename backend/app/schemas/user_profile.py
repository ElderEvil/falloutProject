from datetime import datetime

from pydantic import UUID4, field_validator
from sqlmodel import SQLModel

from app.core.notification_preferences import validate_notification_preferences
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

    @field_validator("preferences")
    @classmethod
    def validate_preferences(cls, preferences: dict | None) -> dict | None:
        if preferences is not None:
            validate_notification_preferences(preferences)
        return preferences


@optional()
class ProfileUpdateStatistics(SQLModel):
    """For internal use only - updating statistics."""

    total_dwellers_created: int | None = None
    total_caps_earned: int | None = None
    total_explorations: int | None = None
    total_rooms_built: int | None = None
    total_dwellers_born: int | None = None
    total_dwellers_died: int | None = None
    deaths_by_health: int | None = None
    deaths_by_radiation: int | None = None
    deaths_by_incident: int | None = None
    deaths_by_exploration: int | None = None
    deaths_by_combat: int | None = None
