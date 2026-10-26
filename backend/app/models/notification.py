from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from app.core.enums import NotificationPriority, NotificationType
from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class NotificationBase(SQLModel):
    user_id: UUID = Field(foreign_key="user.id", index=True)
    vault_id: UUID | None = Field(
        default=None,
        foreign_key="vault.id",
        index=True,
        ondelete="CASCADE",  # Cascade delete when vault is deleted
    )

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

    def __str__(self) -> str:
        return f"{self.title} ({str(self.notification_type).replace('_', ' ')})"


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
