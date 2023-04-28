from app.crud.base import CRUDBase
from app.models.outfit import Outfit, OutfitCreate, OutfitUpdate


class CRUDOutfit(CRUDBase[Outfit, OutfitCreate, OutfitUpdate]):
    ...


outfit = CRUDOutfit(Outfit)
