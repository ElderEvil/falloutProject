"""Exploration models for wasteland expeditions."""

from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


def get_utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.utcnow()


class ExplorationStatus(StrEnum):
    """Status of a wasteland exploration."""

    ACTIVE = "active"
    COMPLETED = "completed"
    RECALLED = "recalled"


class ExplorationBase(SQLModel):
    """Base model for explorations."""

    duration: int = Field(ge=1, le=24, description="Duration in hours")
    start_time: datetime = Field(default_factory=get_utc_now)
    end_time: datetime | None = Field(default=None)
    status: ExplorationStatus = Field(default=ExplorationStatus.ACTIVE, index=True)

    # Journey log and events
    events: list[dict] = Field(default_factory=list, sa_column=sa.Column(JSONB))
    loot_collected: list[dict] = Field(default_factory=list, sa_column=sa.Column(JSONB))

    # Stats at start (for calculations)
    dweller_strength: int = Field(ge=1, le=10)
    dweller_perception: int = Field(ge=1, le=10)
    dweller_endurance: int = Field(ge=1, le=10)
    dweller_charisma: int = Field(ge=1, le=10)
    dweller_intelligence: int = Field(ge=1, le=10)
    dweller_agility: int = Field(ge=1, le=10)
    dweller_luck: int = Field(ge=1, le=10)

    # Results
    total_distance: int = Field(default=0, ge=0, description="Distance traveled in miles")
    total_caps_found: int = Field(default=0, ge=0)
    enemies_encountered: int = Field(default=0, ge=0)


class Exploration(BaseUUIDModel, ExplorationBase, TimeStampMixin, table=True):
    """Exploration model with relationships."""

    vault_id: UUID4 = Field(foreign_key="vault.id", index=True)
    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True)

    def is_active(self) -> bool:
        """Check if exploration is still active."""
        return self.status == ExplorationStatus.ACTIVE

    def is_completed(self) -> bool:
        """Check if exploration is completed."""
        return self.status == ExplorationStatus.COMPLETED

    def elapsed_time_seconds(self) -> int:
        """Calculate elapsed time in seconds."""
        now = datetime.utcnow()
        return int((now - self.start_time).total_seconds())

    def progress_percentage(self) -> float:
        """Calculate progress as percentage (0-100)."""
        if not self.is_active():
            return 100.0
        elapsed = self.elapsed_time_seconds()
        total = self.duration * 3600  # hours to seconds
        return min(100.0, (elapsed / total) * 100)

    def time_remaining_seconds(self) -> int:
        """Calculate time remaining in seconds."""
        if not self.is_active():
            return 0
        total_seconds = self.duration * 3600
        elapsed = self.elapsed_time_seconds()
        return max(0, total_seconds - elapsed)

    def should_generate_event(self, last_event_time: datetime | None = None) -> bool:
        """Check if a new event should be generated (every ~10 minutes)."""
        if not self.is_active():
            return False

        if not last_event_time:
            # First event should happen after 5-10 minutes
            return self.elapsed_time_seconds() >= 300

        now = datetime.utcnow()
        time_since_last_event = (now - last_event_time).total_seconds()
        return time_since_last_event >= 600  # 10 minutes

    def complete(self) -> None:
        """Mark exploration as completed."""
        self.status = ExplorationStatus.COMPLETED
        self.end_time = datetime.utcnow()

    def recall(self) -> None:
        """Mark exploration as recalled (early return)."""
        self.status = ExplorationStatus.RECALLED
        self.end_time = datetime.utcnow()

    def add_event(self, event_type: str, description: str, loot: dict | None = None) -> None:
        """Add an event to the journey log."""
        event = {
            "type": event_type,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "time_elapsed_hours": round(self.elapsed_time_seconds() / 3600, 2),
        }
        if loot:
            event["loot"] = loot
        self.events.append(event)

    def add_loot(self, item_name: str, quantity: int = 1, rarity: str = "common") -> None:
        """Add loot to the collected items."""
        self.loot_collected.append(
            {
                "item_name": item_name,
                "quantity": quantity,
                "rarity": rarity,
                "found_at": datetime.utcnow().isoformat(),
            }
        )
