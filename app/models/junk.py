from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase
from app.schemas.common import JunkType, Rarity

if TYPE_CHECKING:
    from app.models.storage import Storage


class JunkBase(ItemBase):
    junk_type: JunkType
    description: str

    _value_by_rarity = {
        Rarity.common: 2,
        Rarity.rare: 50,
        Rarity.legendary: 200,
    }


class Junk(BaseUUIDModel, JunkBase, TimeStampMixin, table=True):
    storage_id: UUID4 = Field(default=None, nullable=True, foreign_key="storage.id")
    storage: "Storage" = Relationship(back_populates="junk_items")

    def __str__(self):
        return self.name
