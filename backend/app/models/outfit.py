from typing import TYPE_CHECKING, Optional

from pydantic import UUID4
from sqlmodel import Column, Enum, Field, Relationship

from app.core.enums import GenderEnum, OutfitTypeEnum
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.storage import Storage


class OutfitBase(ItemBase):
    outfit_type: OutfitTypeEnum = Field(sa_column=Column(Enum(OutfitTypeEnum)))
    gender: GenderEnum | None = Field(default=None, nullable=True)
    fire_resist: float = Field(default=0.0, ge=0.0, le=1.0, description="Share of fire damage the outfit removes")
    radiation_resist: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        nullable=True,
        description="Share of external radiation removed; None falls back to the outfit type/name table",
    )

    def __str__(self):
        return f"{self.name}"


class Outfit(BaseUUIDModel, OutfitBase, TimeStampMixin, table=True):
    dweller_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="dweller.id", index=True)
    dweller: Optional["Dweller"] = Relationship(back_populates="outfit")
    storage_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="storage.id")
    storage: "Storage" = Relationship(back_populates="outfits")
