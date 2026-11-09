"""Pydantic schemas for pregnancy management."""

from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel
from sqlmodel.main import SQLModelConfig

from app.core.enums import PregnancyStatusEnum
from app.models.pregnancy import PregnancyBase


class PregnancyCreate(SQLModel):
    """Schema for creating a new pregnancy."""

    mother_id: UUID
    father_id: UUID


class PregnancyUpdate(SQLModel):
    """Schema for updating a pregnancy."""

    status: PregnancyStatusEnum | None = None
    due_at: datetime | None = None


class PregnancyRead(PregnancyBase):
    """Schema for reading a pregnancy."""

    id: UUID
    progress_percentage: float
    time_remaining_seconds: int
    is_due: bool

    model_config = SQLModelConfig(from_attributes=True, use_enum_values=True)


class PregnancyProgress(SQLModel):
    """Pregnancy progress information."""

    id: UUID
    mother_id: UUID
    father_id: UUID
    status: PregnancyStatusEnum
    conceived_at: datetime
    due_at: datetime
    progress_percentage: float
    time_remaining_seconds: int
    is_due: bool

    model_config = SQLModelConfig(use_enum_values=True)


class DeliveredChild(SQLModel):
    """A newborn born during delivery."""

    id: UUID
    first_name: str
    last_name: str | None


class DeliveryResult(SQLModel):
    """Result of a pregnancy delivery."""

    pregnancy_id: UUID
    children: list[DeliveredChild]
    message: str
