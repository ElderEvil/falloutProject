from sqlmodel import Field

from app.models.item import ItemBase
from app.schemas.common_schema import Gender, OutfitType


class OutfitBase(ItemBase):
    outfit_type: OutfitType = OutfitType.common
    gender: Gender | None = None


class Outfit(OutfitBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
