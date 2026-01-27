from typing import TYPE_CHECKING

from pydantic import UUID4, model_validator
from sqlmodel import Field, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase
from app.schemas.common import JunkTypeEnum, RarityEnum

if TYPE_CHECKING:
    from app.models.storage import Storage


class JunkBase(ItemBase):
    junk_type: JunkTypeEnum
    description: str = Field(min_length=3, max_length=255)

    _value_by_rarity = {
        RarityEnum.COMMON: 2,
        RarityEnum.RARE: 50,
        RarityEnum.LEGENDARY: 200,
    }

    @model_validator(mode="before")
    @classmethod
    def set_junk_value(cls, data: dict) -> dict:
        """Set junk value based on rarity if not provided."""
        if isinstance(data, dict) and data.get("value") is None:
            rarity = data.get("rarity")
            if rarity:
                data["value"] = cls._value_by_rarity.get(rarity, 2)
        return data


class Junk(BaseUUIDModel, JunkBase, TimeStampMixin, table=True):
    storage_id: UUID4 = Field(default=None, nullable=True, foreign_key="storage.id")
    storage: "Storage" = Relationship(back_populates="junk_items")

    def __str__(self):
        return self.name
