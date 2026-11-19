from typing import TYPE_CHECKING, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class Pet(BaseUUIDModel, ItemBase, TimeStampMixin, table=True):
    """A pet owned by a vault, equippable to a dweller.

    Inventory entity like weapons/outfits: lives in vault storage or on a dweller (CHECK
    enforces the XOR). Effect bonuses are catalog-resolved, so no effect columns exist.
    """

    __table_args__ = (
        sa.CheckConstraint(
            "dweller_id IS NULL OR storage_id IS NULL",
            name="ck_pet_dweller_storage_xor",
        ),
    )

    dweller_id: UUID | None = Field(default=None, nullable=True, foreign_key="dweller.id", index=True)
    dweller: Optional["Dweller"] = Relationship(back_populates="pet")
    storage_id: UUID | None = Field(default=None, nullable=True, foreign_key="storage.id", index=True)
    legacy_item_id: UUID | None = Field(default=None, nullable=True, index=True, unique=True)

    def __str__(self):
        return f"{self.name}"
