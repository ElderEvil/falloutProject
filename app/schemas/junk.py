from datetime import datetime

from app.models.junk import JunkBase
from app.schemas.item import ItemUpdate


class JunkCreate(JunkBase):
    pass


class JunkRead(JunkBase):
    id: int
    created_at: datetime
    updated_at: datetime


class JunkUpdate(ItemUpdate):
    junk_type: str | None = None
    description: str | None = None
