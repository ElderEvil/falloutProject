from datetime import datetime
from uuid import uuid4

from pydantic import UUID4
from sqlmodel import SQLModel, Field


class TimeStampMixin(SQLModel):
    created_at: datetime | None = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )


class BaseUUIDModel(SQLModel):
    id: UUID4 = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )


class SPECIAL(SQLModel):
    strength: int = Field(..., ge=1, le=10)
    perception: int = Field(..., ge=1, le=10)
    endurance: int = Field(..., ge=1, le=10)
    charisma: int = Field(..., ge=1, le=10)
    intelligence: int = Field(..., ge=1, le=10)
    agility: int = Field(..., ge=1, le=10)
    luck: int = Field(..., ge=1, le=10)
