from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class Pet(BaseUUIDModel, ItemBase, TimeStampMixin, table=True):
    """A pet owned by a vault, equippable to a dweller.

    Pets are inventory entities like weapons and outfits: they live in a vault's
    storage or on one of its dwellers (the CHECK constraint enforces the XOR).
    Effect bonuses are catalog-resolved in Phase B, so no effect columns exist.
    """

    __table_args__ = (
        sa.CheckConstraint(
            "dweller_id IS NULL OR storage_id IS NULL",
            name="ck_pet_dweller_storage_xor",
        ),
    )

    dweller_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="dweller.id", index=True)
    dweller: Optional["Dweller"] = Relationship(back_populates="pet")
    storage_id: UUID4 | None = Field(default=None, nullable=True, foreign_key="storage.id")
    legacy_item_id: UUID4 | None = Field(default=None, nullable=True, index=True, unique=True)

    def __str__(self):
        return f"{self.name}"
