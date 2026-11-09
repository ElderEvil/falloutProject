from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship

from app.core.enums import JunkTypeEnum
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase

if TYPE_CHECKING:
    from app.models.storage import Storage


class JunkBase(ItemBase):
    junk_type: JunkTypeEnum
    description: str = Field(min_length=3, max_length=255)


class Junk(BaseUUIDModel, JunkBase, TimeStampMixin, table=True):
    storage_id: UUID | None = Field(default=None, nullable=True, foreign_key="storage.id")
    storage: "Storage" = Relationship(back_populates="junk_items")

    def __str__(self):
        return self.name
