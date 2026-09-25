"""Exploration models for wasteland expeditions."""

from datetime import datetime, timedelta
from enum import StrEnum

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy import orm
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.enums import ExpeditionRunStatus
from app.models.base import BaseUUIDModel, TimeStampMixin

# The trip home takes half the time the dweller spent exploring.
RETURN_LEG_FRACTION = 0.5


def get_utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.utcnow()


class ExplorationStatus(StrEnum):
    """Status of a wasteland exploration."""

    ACTIVE = "active"
    RETURNING = "returning"
    COMPLETED = "completed"
    RECALLED = "recalled"


# Statuses that still occupy the dweller; the run is not finished until it leaves this set.
IN_PROGRESS_STATUSES: tuple[ExplorationStatus, ...] = (ExplorationStatus.ACTIVE, ExplorationStatus.RETURNING)


class ExplorationBase(SQLModel):
    """Base model for explorations."""

    duration: int = Field(ge=1, le=24, description="Duration in hours")
    start_time: datetime = Field(default_factory=get_utc_now)
    end_time: datetime | None = Field(default=None)
    status: ExplorationStatus = Field(default=ExplorationStatus.ACTIVE, index=True)

    # Return leg: set when exploring ends, cleared into the terminal outcome on arrival.
    return_started_at: datetime | None = Field(default=None)
    return_completes_at: datetime | None = Field(default=None)
    recalled_early: bool = Field(default=False)

    # Journey log and events
    events: list[dict] = Field(default_factory=list, sa_column=sa.Column(JSONB))
    loot_collected: list[dict] = Field(default_factory=list, sa_column=sa.Column(JSONB))
    # Overflow loot awaiting a per-item take/sell decision on the return screen.
    unclaimed_loot: list[dict] = Field(
        default_factory=list,
        sa_column=sa.Column(JSONB, nullable=False),
    )

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

    # Medical supplies
    stimpaks: int = Field(default=0, ge=0, description="Stimpaks taken on exploration")
    radaways: int = Field(default=0, ge=0, description="Radaways taken on exploration")


class Exploration(BaseUUIDModel, ExplorationBase, TimeStampMixin, table=True):
    """Exploration model with relationships."""

    vault_id: UUID4 = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")

    def is_active(self) -> bool:
        """Check if exploration is still active."""
        return self.status == ExplorationStatus.ACTIVE

    def is_returning(self) -> bool:
        """Check if the dweller is on the way home from the wasteland."""
        return self.status == ExplorationStatus.RETURNING

    def is_in_progress(self) -> bool:
        """Check if the run is ongoing, whether exploring or returning."""
        return self.status in IN_PROGRESS_STATUSES

    def is_completed(self) -> bool:
        """Check if exploration is completed."""
        return self.status == ExplorationStatus.COMPLETED

    def elapsed_time_seconds(self) -> int:
        """Calculate elapsed time in seconds."""
        now = datetime.utcnow()
        return int((now - self.start_time).total_seconds())

    def exploring_seconds(self) -> int:
        """Seconds actually spent exploring, capped at the planned duration."""
        end = self.return_started_at or datetime.utcnow()
        return min(max(0, int((end - self.start_time).total_seconds())), self.duration * 3600)

    def exploring_progress_percentage(self) -> float:
        """Exploration progress at the moment exploring ended (0-100)."""
        total = self.duration * 3600
        if total <= 0:
            return 100.0
        return min(100.0, (self.exploring_seconds() / total) * 100)

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

    def start_return(self, *, recalled: bool = False) -> None:
        """Begin the trip home, lasting half the time spent exploring."""
        now = datetime.utcnow()
        exploring_seconds = self.exploring_seconds()
        self.return_started_at = now
        self.return_completes_at = now + timedelta(seconds=int(exploring_seconds * RETURN_LEG_FRACTION))
        self.recalled_early = recalled
        self.status = ExplorationStatus.RETURNING

    def return_time_remaining_seconds(self) -> int:
        """Seconds until the dweller arrives home; 0 unless returning."""
        if not self.is_returning() or self.return_completes_at is None:
            return 0
        return max(0, int((self.return_completes_at - datetime.utcnow()).total_seconds()))

    def finalize_return(self) -> None:
        """Finish the run once the dweller is home, preserving the outcome."""
        if self.recalled_early:
            self.recall()
        else:
            self.complete()

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

    def add_event(
        self,
        event_type: str,
        description: str,
        loot: dict | None = None,
        location_name: str | None = None,
        location_id: UUID4 | None = None,
        coord_x: float | None = None,
        coord_y: float | None = None,
        health_loss: int | None = None,
        health_restored: int | None = None,
        radiation_gain: int | None = None,
        radiation_removed: int | None = None,
    ) -> dict:
        """Add an event to the journey log.

        Returns the created event record so callers can publish it (e.g. via SSE).
        """
        event = {
            "type": event_type,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "time_elapsed_hours": round(self.elapsed_time_seconds() / 3600, 2),
        }
        if loot:
            event["loot"] = loot
        if location_name:
            event["location_name"] = location_name
        if location_id is not None:
            event["location_id"] = str(location_id)
        if coord_x is not None:
            event["coord_x"] = coord_x
        if coord_y is not None:
            event["coord_y"] = coord_y
        if health_loss is not None:
            event["health_loss"] = health_loss
        if health_restored is not None:
            event["health_restored"] = health_restored
        if radiation_gain is not None:
            event["radiation_gain"] = radiation_gain
        if radiation_removed is not None:
            event["radiation_removed"] = radiation_removed
        self.events.append(event)
        # Flag the field as modified so SQLAlchemy tracks the change
        orm.attributes.flag_modified(self, "events")
        return event

    def add_loot(self, item_name: str, quantity: int = 1, rarity: str = "common", item_type: str = "junk") -> None:
        """Add loot to the collected items."""
        self.loot_collected.append(
            {
                "item_name": item_name,
                "quantity": quantity,
                "rarity": rarity,
                "item_type": item_type,
                "found_at": datetime.utcnow().isoformat(),
            }
        )
        # Flag the field as modified so SQLAlchemy tracks the change
        orm.attributes.flag_modified(self, "loot_collected")


# Statuses that still accept room resolutions; at most one open run per exploration
# and per vault+site (partial unique indexes below).
OPEN_STATUSES: tuple[ExpeditionRunStatus, ...] = (ExpeditionRunStatus.ENTERED, ExpeditionRunStatus.IN_ROOM)

# Statuses that end a run and start the per-vault+site cooldown (D2-B).
TERMINAL_STATUSES: tuple[ExpeditionRunStatus, ...] = (
    ExpeditionRunStatus.CLEARED,
    ExpeditionRunStatus.RETREATED,
    ExpeditionRunStatus.DIED,
)


class ExpeditionRun(BaseUUIDModel, TimeStampMixin, table=True):
    """One attempt at an expedition site: room cursor plus cooldown record."""

    __table_args__ = (
        sa.Index(
            "uq_expeditionrun_open_exploration",
            "exploration_id",
            unique=True,
            postgresql_where=sa.text("status IN ('ENTERED', 'IN_ROOM')"),
            sqlite_where=sa.text("status IN ('ENTERED', 'IN_ROOM')"),
        ),
        sa.Index(
            "uq_expeditionrun_open_vault_site",
            "vault_id",
            "site_id",
            unique=True,
            postgresql_where=sa.text("status IN ('ENTERED', 'IN_ROOM')"),
            sqlite_where=sa.text("status IN ('ENTERED', 'IN_ROOM')"),
        ),
    )

    exploration_id: UUID4 = Field(foreign_key="exploration.id", index=True, ondelete="CASCADE")
    vault_id: UUID4 = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")
    site_id: str = Field(max_length=64, index=True)
    room_cursor: int = Field(default=0, ge=0)
    status: ExpeditionRunStatus = Field(default=ExpeditionRunStatus.ENTERED, index=True)
    flags: dict = Field(default_factory=dict, sa_column=sa.Column(JSONB))
    # Terminal timestamp: set when the run reaches any terminal state
    # (CLEARED/RETREATED/DIED) and backs the 7-day per-vault+site cooldown.
    finished_at: datetime | None = Field(default=None)

    def is_open(self) -> bool:
        """Return whether the run still accepts room resolutions."""
        return self.status in OPEN_STATUSES
