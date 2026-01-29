from typing import TYPE_CHECKING, Optional

from pydantic import UUID4
from sqlmodel import Column, Enum, Field, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase
from app.schemas.common import GenderEnum, OutfitTypeEnum

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.storage import Storage


class OutfitBase(ItemBase):
    outfit_type: OutfitTypeEnum = Field(sa_column=Column(Enum(OutfitTypeEnum)))
    gender: GenderEnum | None = Field(default=None, nullable=True)

    def __str__(self):
        return f"{self.name}"


class Outfit(BaseUUIDModel, OutfitBase, TimeStampMixin, table=True):
    dweller_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="dweller.id")
    dweller: Optional["Dweller"] = Relationship(back_populates="outfit")
    storage_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="storage.id")
    storage: "Storage" = Relationship(back_populates="outfits")
