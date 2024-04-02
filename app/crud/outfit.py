from app.crud.item_base import CRUDEquippableItem
from app.models.outfit import Outfit
from app.schemas.outfit import OutfitCreate, OutfitUpdate


class CRUDOutfit(CRUDEquippableItem[Outfit, OutfitCreate, OutfitUpdate]):
    pass


outfit = CRUDOutfit(Outfit)
