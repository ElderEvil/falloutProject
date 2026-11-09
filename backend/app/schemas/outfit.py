from datetime import datetime
from uuid import UUID

from app.models.outfit import OutfitBase
from app.schemas.item import ItemUpdate
from app.utils.partial import optional


class OutfitCreate(OutfitBase):
    # Optional fields - can be omitted, but if provided must be valid UUID
    storage_id: UUID | None = None


class OutfitRead(OutfitBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    dweller_id: UUID | None = None
    storage_id: UUID | None = None
    # Read-time workshop summary; outfits carry no flavor-text column.
    description: str | None = None


@optional()
class OutfitUpdate(ItemUpdate, OutfitBase):
    dweller_id: UUID | None = None
    storage_id: UUID | None = None
