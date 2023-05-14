from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.schemas.dweller import DwellerCreate, DwellerUpdate


class CRUDDweller(CRUDBase[Dweller, DwellerCreate, DwellerUpdate]):
    ...

    def add_exp(self):
        ...  # TODO: Add exp to dweller


dweller = CRUDDweller(Dweller)
