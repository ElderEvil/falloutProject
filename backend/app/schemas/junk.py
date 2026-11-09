from datetime import datetime
from uuid import UUID

from app.models.junk import JunkBase
from app.schemas.item import ItemUpdate
from app.utils.partial import optional


class JunkCreate(JunkBase):
    storage_id: UUID | None = None


class JunkRead(JunkBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    storage_id: UUID | None = None


@optional()
class JunkUpdate(ItemUpdate, JunkBase):
    storage_id: UUID | None = None
