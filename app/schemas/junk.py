from datetime import datetime

from pydantic import UUID4

from app.models.junk import JunkBase
from app.schemas.item import ItemUpdate


class JunkCreate(JunkBase):
    pass


class JunkRead(JunkBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class JunkUpdate(ItemUpdate):
    junk_type: str | None = None
    description: str | None = None
