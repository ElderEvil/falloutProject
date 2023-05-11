from sqlmodel import Field

from app.models.base import TimeStampMixin
from app.models.item import ItemBase
from app.schemas.common import Gender, OutfitType


class OutfitBase(ItemBase):
    outfit_type: OutfitType = OutfitType.common
    gender: Gender | None = None


class Outfit(OutfitBase, TimeStampMixin, table=True):
    id: int | None = Field(default=None, primary_key=True)
