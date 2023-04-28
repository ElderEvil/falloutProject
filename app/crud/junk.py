from app.crud.base import CRUDBase
from app.models.junk import Junk
from app.schemas.junk import JunkCreate, JunkUpdate


class CRUDJunk(CRUDBase[Junk, JunkCreate, JunkUpdate]):
    ...


junk = CRUDJunk(Junk)
