"""Incident models for combat events and vault disasters."""

from datetime import datetime
from enum import StrEnum

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class IncidentType(StrEnum):
    """Types of incidents that can occur in the vault."""

    # Enemy attacks
    RAIDER_ATTACK = "raider_attack"
    RADROACH_INFESTATION = "radroach_infestation"
    MOLE_RAT_ATTACK = "mole_rat_attack"
    DEATHCLAW_ATTACK = "deathclaw_attack"
    FERAL_GHOUL_ATTACK = "feral_ghoul_attack"

    # Disasters
    FIRE = "fire"
    RADIATION_LEAK = "radiation_leak"
    ELECTRICAL_FAILURE = "electrical_failure"
    WATER_CONTAMINATION = "water_contamination"


class IncidentStatus(StrEnum):
    """Status of an incident."""

    ACTIVE = "active"
    SPREADING = "spreading"
    RESOLVED = "resolved"
    FAILED = "failed"


class IncidentBase(SQLModel):
    """Base model for incidents."""

    type: IncidentType = Field(index=True)
    status: IncidentStatus = Field(default=IncidentStatus.ACTIVE, index=True)
    difficulty: int = Field(ge=1, le=10, description="Difficulty level of the incident")
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime | None = Field(default=None)
    duration: int = Field(default=60, ge=10, description="Duration in seconds before auto-spreading")

    # Damage tracking
    damage_dealt: int = Field(default=0, ge=0, description="Total damage dealt to dwellers")
    enemies_defeated: int = Field(default=0, ge=0, description="Number of enemies defeated")

    # Loot/rewards
    loot: dict | None = Field(default=None, sa_column=sa.Column(JSONB), description="Rewards from incident")

    # Spread tracking
    rooms_affected: list[str] = Field(default_factory=list, sa_column=sa.Column(JSONB))
    spread_count: int = Field(default=0, ge=0, description="Number of times incident has spread")


class Incident(BaseUUIDModel, IncidentBase, TimeStampMixin, table=True):
    """Incident model with relationships."""

    vault_id: UUID4 = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    room_id: UUID4 = Field(foreign_key="room.id", index=True, ondelete="CASCADE")

    def is_active(self) -> bool:
        """Check if incident is still active."""
        return self.status == IncidentStatus.ACTIVE

    def elapsed_time(self) -> int:
        """Calculate elapsed time since incident started."""
        return int((datetime.utcnow() - self.start_time).total_seconds())

    def should_spread(self) -> bool:
        """Check if incident should spread to adjacent rooms."""
        return self.is_active() and self.elapsed_time() >= self.duration

    def resolve(self, success: bool = True) -> None:  # noqa: FBT001, FBT002
        """Resolve the incident."""
        self.status = IncidentStatus.RESOLVED if success else IncidentStatus.FAILED
        self.end_time = datetime.utcnow()

    def spread_to_room(self, room_id: str) -> None:
        """Mark incident as spreading to a new room."""
        if room_id not in self.rooms_affected:
            self.rooms_affected.append(room_id)
            self.spread_count += 1
            self.status = IncidentStatus.SPREADING
