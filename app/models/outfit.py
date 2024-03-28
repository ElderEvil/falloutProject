from typing import TYPE_CHECKING, Optional

from pydantic import UUID4
from sqlmodel import Field, Relationship, Column, Enum

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase
from app.schemas.common import Gender, OutfitType

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class OutfitBase(ItemBase):
    outfit_type: OutfitType = Field(sa_column=Column(Enum(OutfitType)))
    gender: Gender | None = Field(default=None, nullable=True)


class Outfit(BaseUUIDModel, OutfitBase, TimeStampMixin, table=True):
    dweller_id: UUID4 = Field(default=None, nullable=True, foreign_key="dweller.id")
    dweller: Optional["Dweller"] = Relationship(back_populates="outfit")
