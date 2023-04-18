from app.api.crud.base import CRUDBase
from app.api.models.outfit import Outfit, OutfitCreate, OutfitUpdate


class CRUDOutfit(CRUDBase[Outfit, OutfitCreate, OutfitUpdate]):
    ...


outfit = CRUDOutfit(Outfit)
