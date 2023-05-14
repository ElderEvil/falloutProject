from datetime import datetime

from pydantic import UUID4, Field
from sqlmodel import SQLModel

from app.models.dweller import DwellerBase


class DwellerCreate(DwellerBase):
    pass


class DwellerRead(DwellerBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class DwellerUpdate(SQLModel):
    level: int | None = Field(default=1, ge=1, le=50, nullable=True)
    experience: int | None = 0
    max_health: int | None = 0
    health: int | None = 0
    happiness: int | None = Field(default=50, ge=10, le=100)
    is_adult: bool | None = True
