from app.models.base import TimeStampMixin, BaseUUIDModel
from app.models.item import ItemBase
from app.schemas.common import Gender, OutfitType


class OutfitBase(ItemBase):
    outfit_type: OutfitType = OutfitType.common
    gender: Gender | None = None


class Outfit(BaseUUIDModel, OutfitBase, TimeStampMixin, table=True):
    ...
