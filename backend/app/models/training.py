"""Training model for dweller SPECIAL stat training."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.schemas.common import SPECIALEnum

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.room import Room
    from app.models.vault import Vault


class TrainingStatus(StrEnum):
    """Status of a training session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TrainingBase(SQLModel):
    """Base model for training sessions."""

    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True)
    room_id: UUID4 = Field(foreign_key="room.id", index=True)
    vault_id: UUID4 = Field(foreign_key="vault.id", index=True)

    stat_being_trained: SPECIALEnum
    current_stat_value: int = Field(ge=1, le=10)  # Snapshot at start
    target_stat_value: int = Field(ge=2, le=10)  # Always current + 1

    progress: float = Field(default=0.0, ge=0.0, le=1.0)  # 0.0 to 1.0

    started_at: datetime
    estimated_completion_at: datetime
    completed_at: datetime | None = None

    status: TrainingStatus = Field(default=TrainingStatus.ACTIVE, index=True)


class Training(BaseUUIDModel, TrainingBase, TimeStampMixin, table=True):
    """Training session for a dweller in a training room."""

    # Relationships
    dweller: "Dweller" = Relationship(back_populates="trainings")
    room: "Room" = Relationship()
    vault: "Vault" = Relationship()

    def is_active(self) -> bool:
        """Check if training is currently active."""
        return self.status == TrainingStatus.ACTIVE

    def is_completed(self) -> bool:
        """Check if training has been completed."""
        return self.status == TrainingStatus.COMPLETED

    def is_cancelled(self) -> bool:
        """Check if training was cancelled."""
        return self.status == TrainingStatus.CANCELLED

    def progress_percentage(self) -> float:
        """Get progress as percentage (0-100)."""
        return self.progress * 100

    def time_remaining_seconds(self) -> int:
        """
        Calculate remaining time in seconds.

        Returns:
            Remaining seconds, or 0 if not active or already completed
        """
        if not self.is_active():
            return 0

        now = datetime.utcnow()
        if now >= self.estimated_completion_at:
            return 0

        remaining = (self.estimated_completion_at - now).total_seconds()
        return max(0, int(remaining))

    def is_ready_to_complete(self) -> bool:
        """Check if training duration has elapsed and ready to complete."""
        if not self.is_active():
            return False
        return datetime.utcnow() >= self.estimated_completion_at
