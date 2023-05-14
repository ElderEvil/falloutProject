from sqlmodel import Field, SQLModel

from app.models.base import TimeStampMixin, BaseUUIDModel, SPECIAL
from app.schemas.common import Gender, Rarity


class DwellerBaseWithoutStats(SQLModel):
    first_name: str = Field(..., index=True, min_length=3, max_length=32)
    last_name: str = Field(..., index=True, min_length=3, max_length=32)
    gender: Gender = Field(...)
    rarity: Rarity = Field(...)
    level: int = Field(ge=1, le=50, default=1)
    experience: int = Field(ge=0, default=0)
    max_health: int = Field(ge=50, le=1000, default=50)
    health: int = Field(ge=0, le=1000, default=50)
    happiness: int = Field(ge=10, le=100, default=50)
    is_adult: bool = True


class DwellerBase(DwellerBaseWithoutStats, SPECIAL):
    ...


class Dweller(BaseUUIDModel, DwellerBase, TimeStampMixin, table=True):
    ...
