from datetime import datetime

from pydantic import UUID4

from app.models.junk import JunkBase
from app.schemas.item import ItemUpdate
from app.utils.partial import optional


class JunkCreate(JunkBase):
    pass


class JunkRead(JunkBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


@optional()
class JunkUpdate(ItemUpdate, JunkBase):
    pass
