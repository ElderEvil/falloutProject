"""Barbershop appearance-change schemas."""

from pydantic import UUID4, Field
from sqlmodel import SQLModel
from sqlmodel.main import SQLModelConfig

from app.schemas.dweller import DwellerReadFull


class BarbershopStatus(SQLModel):
    """Availability, fee, and preset swatches for a vault's Barbershop."""

    room_id: UUID4 | None = None
    built: bool
    staffed: bool
    fee: int
    skin_fee: int
    hair_fee: int
    vault_caps: int
    skin_tones: list[str]
    hair_colors: list[str]


class BarbershopChangeRequest(SQLModel):
    """A requested skin-tone / hair-color change."""

    skin_tone: str = Field(min_length=1, max_length=32)
    hair_color: str = Field(min_length=1, max_length=32)

    model_config = SQLModelConfig(extra="forbid")


class BarbershopChangeResponse(SQLModel):
    """Result of a Barbershop appearance change."""

    dweller: DwellerReadFull
    portrait_updated: bool
    fee: int
    remaining_caps: int
