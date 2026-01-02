"""Training schemas for API requests and responses."""

from datetime import datetime

from pydantic import UUID4

from app.models.training import TrainingBase


class TrainingCreate(TrainingBase):
    """Schema for creating a training session."""


class TrainingUpdate(TrainingBase):
    """Schema for updating a training session."""


class TrainingRead(TrainingBase):
    """Schema for reading a training session."""

    id: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrainingStartRequest(TrainingBase):
    """Request to start training a dweller."""

    dweller_id: UUID4
    room_id: UUID4


class TrainingProgress(TrainingBase):
    """Detailed training progress information."""

    id: UUID4
    progress_percentage: float
    time_remaining_seconds: int
    is_ready_to_complete: bool

    class Config:
        from_attributes = True
