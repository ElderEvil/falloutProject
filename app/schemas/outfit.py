from datetime import datetime

from app.models.outfit import OutfitBase
from app.schemas.common import Gender, OutfitType
from app.schemas.item import ItemUpdate


class OutfitCreate(OutfitBase):
    pass


class OutfitRead(OutfitBase):
    id: int
    created_at: datetime
    updated_at: datetime


class OutfitUpdate(ItemUpdate):
    outfit_type: OutfitType | None = None
    gender: Gender | None = None
