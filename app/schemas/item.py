from pydantic import UUID4
from sqlmodel import SQLModel

from app.models.item import ItemBase
from app.schemas.common import Rarity


class ItemCreate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: UUID4


class ItemUpdate(SQLModel):
    name: str | None = None
    rarity: Rarity | None = None
    value: int | None = None
