from datetime import datetime

from pydantic import UUID4

from app.models.outfit import OutfitBase
from app.schemas.item import ItemUpdate
from app.utils.partial import optional


class OutfitCreate(OutfitBase):
    # Optional fields - can be omitted, but if provided must be valid UUID
    storage_id: UUID4 | None = None


class OutfitRead(OutfitBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None


@optional()
class OutfitUpdate(ItemUpdate, OutfitBase):
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None
