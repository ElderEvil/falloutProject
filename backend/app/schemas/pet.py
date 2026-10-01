from datetime import datetime

from pydantic import UUID4

from app.models.item import ItemBase
from app.utils.partial import optional


class PetCreate(ItemBase):
    # Optional fields - can be omitted, but if provided must be valid UUID
    storage_id: UUID4 | None = None


class PetRead(ItemBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None


@optional()
class PetUpdate(ItemBase):
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None
