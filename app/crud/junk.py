from app.crud.base import CRUDBase
from app.models.junk import Junk, JunkCreate, JunkUpdate


class CRUDJunk(CRUDBase[Junk, JunkCreate, JunkUpdate]):
    ...


junk = CRUDJunk(Junk)
