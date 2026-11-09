from uuid import UUID

from app.models.outfit import OutfitBase
from app.schemas.item import ItemUpdate
from app.utils.partial import optional
from app.utils.serialize_types import UTCDateTimeJSON


class OutfitCreate(OutfitBase):
    # Optional fields - can be omitted, but if provided must be valid UUID
    storage_id: UUID | None = None


class OutfitRead(OutfitBase):
    id: UUID
    created_at: UTCDateTimeJSON
    updated_at: UTCDateTimeJSON
    dweller_id: UUID | None = None
    storage_id: UUID | None = None
    # Read-time workshop summary; outfits carry no flavor-text column.
    description: str | None = None


@optional()
class OutfitUpdate(ItemUpdate, OutfitBase):
    dweller_id: UUID | None = None
    storage_id: UUID | None = None
