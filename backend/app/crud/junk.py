from app.crud.item_base import CRUDItem
from app.models.junk import Junk
from app.schemas.junk import JunkCreate, JunkUpdate


class CRUDJunk(CRUDItem[Junk, JunkCreate, JunkUpdate]):
    pass


junk = CRUDJunk(Junk)
