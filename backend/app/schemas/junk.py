from uuid import UUID

from app.models.junk import JunkBase
from app.schemas.item import ItemUpdate
from app.utils.partial import optional
from app.utils.serialize_types import UTCDateTimeJSON


class JunkCreate(JunkBase):
    storage_id: UUID | None = None


class JunkRead(JunkBase):
    id: UUID
    created_at: UTCDateTimeJSON
    updated_at: UTCDateTimeJSON
    storage_id: UUID | None = None


@optional()
class JunkUpdate(ItemUpdate, JunkBase):
    storage_id: UUID | None = None
