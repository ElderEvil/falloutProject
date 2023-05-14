from sqlmodel import SQLModel, Field

from app.models.base import TimeStampMixin, BaseUUIDModel


class DwellerBase(SQLModel):
    first_name: str = Field(..., index=True, min_length=3, max_length=32)
    last_name: str = Field(..., index=True, min_length=3, max_length=32)
    level: int = Field(default=1, ge=1, le=50)
    experience: int = Field(ge=0)
    max_health: int = Field(ge=50, le=1000)
    health: int = Field(ge=0, le=1000)
    happiness: int = Field(default=50, ge=10, le=100)
    is_adult: bool = True


class Dweller(BaseUUIDModel, DwellerBase, TimeStampMixin, table=True):
    ...
