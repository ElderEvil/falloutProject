from datetime import datetime

from pydantic import UUID4, BaseModel, Field

from app.models.outfit import OutfitBase
from app.schemas.item import ItemUpdate
from app.utils.partial import optional


class SPECIALOutfitCreate(BaseModel):
    strength: int = Field(default=0, ge=0, le=7)
    perception: int = Field(default=0, ge=0, le=7)
    endurance: int = Field(default=0, ge=0, le=7)
    charisma: int = Field(default=0, ge=0, le=7)
    intelligence: int = Field(default=0, ge=0, le=7)
    agility: int = Field(default=0, ge=0, le=7)
    luck: int = Field(default=0, ge=0, le=7)


class OutfitCreate(OutfitBase, SPECIALOutfitCreate):
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
