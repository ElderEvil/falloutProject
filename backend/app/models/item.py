from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4, model_validator
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel
from app.schemas.common import ItemTypeEnum, RarityEnum

if TYPE_CHECKING:
    from app.models.storage import Storage


class ItemBase(SQLModel):
    name: str = Field(index=True, min_length=3, max_length=32)
    rarity: RarityEnum
    value: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=255)

    _value_by_rarity = {
        RarityEnum.COMMON: 10,
        RarityEnum.RARE: 100,
        RarityEnum.LEGENDARY: 500,
    }

    @model_validator(mode="before")
    @classmethod
    def set_default_value(cls, data: dict) -> dict:
        """Set default value based on rarity if not provided."""
        if isinstance(data, dict) and data.get("value") is None:
            rarity = data.get("rarity")
            if rarity:
                # Convert string to RarityEnum if needed
                if isinstance(rarity, str):
                    try:
                        rarity = RarityEnum(rarity)
                    except (ValueError, KeyError):
                        # Fall back to default if conversion fails
                        data["value"] = 10
                        return data
                # Lookup using enum key
                data["value"] = cls._value_by_rarity.get(rarity, 10)
        return data


class Item(BaseUUIDModel, ItemBase, table=True):
    """Generic inventory item for categories without dedicated equipment models."""

    __table_args__ = (
        sa.CheckConstraint(
            "item_type IN ('misc', 'weapon', 'outfit', 'junk', 'consumable', 'lunchbox', 'pet', 'dweller')",
            name="ck_item_item_type",
        ),
    )

    item_type: ItemTypeEnum = Field(
        default=ItemTypeEnum.MISC,
        sa_column=sa.Column(sa.String(length=32), nullable=False),
    )
    storage_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="storage.id")
    storage: "Storage" = Relationship(back_populates="items")
