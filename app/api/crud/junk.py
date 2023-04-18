from app.api.crud.base import CRUDBase
from app.api.models.junk import Junk, JunkCreate, JunkUpdate


class CRUDJunk(CRUDBase[Junk, JunkCreate, JunkUpdate]):
    ...


junk = CRUDJunk(Junk)
