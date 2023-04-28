from app.models.outfit import OutfitBase
from app.schemas.common_schema import Gender, OutfitType
from app.schemas.item import ItemUpdate


class OutfitCreate(OutfitBase):
    pass


class OutfitRead(OutfitBase):
    id: int


class OutfitUpdate(ItemUpdate):
    outfit_type: OutfitType | None = None
    gender: Gender | None = None
