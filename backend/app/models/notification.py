from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class NotificationType(StrEnum):
    """Types of notifications"""

    # Dweller events
    EXPLORATION_UPDATE = "exploration_update"  # Found item, low health, etc.
    EXPLORATION_COMPLETE = "exploration_complete"
    LEVEL_UP = "level_up"
    TRAINING_COMPLETE = "training_complete"
    TRAINING_STARTED = "training_started"

    # Social events
    RELATIONSHIP_FORMED = "relationship_formed"
    PREGNANCY_DETECTED = "pregnancy_detected"
    BABY_BORN = "baby_born"

    # Combat events
    COMBAT_STARTED = "combat_started"
    COMBAT_VICTORY = "combat_victory"
    COMBAT_DEFEAT = "combat_defeat"
    DWELLER_INJURED = "dweller_injured"

    # Resource events
    RESOURCE_LOW = "resource_low"
    RESOURCE_CRITICAL = "resource_critical"
    POWER_OUTAGE = "power_outage"

    # System events
    QUEST_COMPLETE = "quest_complete"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    RADIO_NEW_DWELLER = "radio_new_dweller"


class NotificationPriority(StrEnum):
    INFO = "info"  # FYI, dismissible
    NORMAL = "normal"  # Standard notification
    HIGH = "high"  # Important, deserves attention
    URGENT = "urgent"  # Critical, needs immediate action


class NotificationBase(SQLModel):
    user_id: UUID = Field(foreign_key="user.id", index=True)
    vault_id: UUID | None = Field(default=None, foreign_key="vault.id", index=True)

    # Source of notification (null for system notifications)
    from_dweller_id: UUID | None = Field(default=None, foreign_key="dweller.id", index=True)

    notification_type: NotificationType = Field(index=True)
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, index=True)

    title: str = Field(max_length=200)
    message: str = Field(max_length=1000)

    is_read: bool = Field(default=False, index=True)
    is_dismissed: bool = Field(default=False, index=True)  # User dismissed it


class Notification(BaseUUIDModel, NotificationBase, table=True):
    # Extra context data (dweller stats, items found, etc.)
    # Renamed from 'metadata' to avoid SQLAlchemy reserved name
    meta_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    read_at: datetime | None = None

    # Relationships
    from_dweller: Optional["Dweller"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Notification.from_dweller_id]"}
    )


class NotificationCreate(NotificationBase):
    meta_data: dict[str, Any] | None = None


class NotificationRead(NotificationBase):
    id: UUID
    meta_data: dict[str, Any] | None = None
    created_at: datetime
    read_at: datetime | None


class NotificationUpdate(SQLModel):
    is_read: bool | None = None
    is_dismissed: bool | None = None
    read_at: datetime | None = None
