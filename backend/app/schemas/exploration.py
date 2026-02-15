"""Exploration schemas for wasteland expeditions."""

from datetime import datetime

from pydantic import UUID4, Field
from sqlmodel import SQLModel

from app.models.exploration import ExplorationStatus


class ExplorationBase(SQLModel):
    """Base exploration schema."""

    duration: int = Field(ge=1, le=24, description="Duration in hours")


class ExplorationCreate(ExplorationBase):
    """Schema for creating a new exploration."""

    dweller_id: UUID4
    vault_id: UUID4
    duration: int = Field(default=4, ge=1, le=24)
    stimpaks: int = Field(default=0, ge=0)
    radaways: int = Field(default=0, ge=0)


class ExplorationUpdate(SQLModel):
    """Schema for updating an exploration."""

    status: ExplorationStatus | None = None
    end_time: datetime | None = None
    total_distance: int | None = None
    total_caps_found: int | None = None
    enemies_encountered: int | None = None


class ExplorationRead(ExplorationBase):
    """Schema for reading exploration data."""

    id: UUID4
    vault_id: UUID4
    dweller_id: UUID4
    status: ExplorationStatus
    start_time: datetime
    end_time: datetime | None
    events: list[dict]
    loot_collected: list[dict]
    total_distance: int
    total_caps_found: int
    enemies_encountered: int
    created_at: datetime
    updated_at: datetime

    # SPECIAL stats at start
    dweller_strength: int
    dweller_perception: int
    dweller_endurance: int
    dweller_charisma: int
    dweller_intelligence: int
    dweller_agility: int
    dweller_luck: int
    stimpaks: int
    radaways: int


class ExplorationReadShort(SQLModel):
    """Schema for reading exploration data (short version for lists)."""

    id: UUID4
    vault_id: UUID4
    dweller_id: UUID4
    status: ExplorationStatus
    start_time: datetime
    end_time: datetime | None
    duration: int
    total_distance: int
    total_caps_found: int
    enemies_encountered: int
    stimpaks: int
    radaways: int


class ExplorationProgress(SQLModel):
    """Schema for exploration progress updates."""

    id: UUID4
    status: ExplorationStatus
    progress_percentage: float = Field(ge=0, le=100)
    time_remaining_seconds: int
    elapsed_time_seconds: int
    events: list[dict]
    loot_collected: list[dict]
    stimpaks: int
    radaways: int


class ExplorationEvent(SQLModel):
    """Schema for exploration events."""

    type: str
    description: str
    timestamp: str
    time_elapsed_hours: float
    loot: dict | None = None


class ExplorationSendRequest(SQLModel):
    """Schema for sending a dweller to wasteland."""

    dweller_id: UUID4
    duration: int = Field(default=4, ge=1, le=24, description="Duration in hours")
    stimpaks: int = Field(default=0, ge=0, le=25, description="Number of Stimpaks to bring")
    radaways: int = Field(default=0, ge=0, le=25, description="Number of Radaways to bring")


class ExplorationRecallRequest(SQLModel):
    """Schema for recalling a dweller from wasteland."""

    exploration_id: UUID4


class ExplorationCompleteResponse(SQLModel):
    """Schema for completed exploration response."""

    exploration: ExplorationRead
    rewards_summary: dict = Field(description="Summary of rewards: {caps: int, items: list, experience: int}")
