"""Pydantic schemas for pregnancy management."""

from datetime import datetime

from pydantic import UUID4, ConfigDict
from sqlmodel import SQLModel

from app.models.pregnancy import PregnancyBase
from app.schemas.common import PregnancyStatusEnum


class PregnancyCreate(SQLModel):
    """Schema for creating a new pregnancy."""

    mother_id: UUID4
    father_id: UUID4


class PregnancyUpdate(SQLModel):
    """Schema for updating a pregnancy."""

    status: PregnancyStatusEnum | None = None
    due_at: datetime | None = None


class PregnancyRead(PregnancyBase):
    """Schema for reading a pregnancy."""

    id: UUID4
    progress_percentage: float
    time_remaining_seconds: int
    is_due: bool

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class PregnancyProgress(SQLModel):
    """Pregnancy progress information."""

    id: UUID4
    mother_id: UUID4
    father_id: UUID4
    status: PregnancyStatusEnum
    conceived_at: datetime
    due_at: datetime
    progress_percentage: float
    time_remaining_seconds: int
    is_due: bool

    model_config = ConfigDict(use_enum_values=True)


class DeliveryResult(SQLModel):
    """Result of a pregnancy delivery."""

    pregnancy_id: UUID4
    child_id: UUID4
    message: str
