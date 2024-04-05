from datetime import datetime

from pydantic import UUID4, Field, BaseModel

from app.models.outfit import OutfitBase
from app.schemas.common import Gender, OutfitType
from app.schemas.item import ItemUpdate


class SPECIALOutfitCreate(BaseModel):
    strength: int = Field(default=0, ge=0, le=7)
    perception: int =  Field(default=0, ge=0, le=7)
    endurance: int =  Field(default=0, ge=0, le=7)
    charisma: int =  Field(default=0, ge=0, le=7)
    intelligence: int =  Field(default=0, ge=0, le=7)
    agility: int =  Field(default=0, ge=0, le=7)
    luck: int =  Field(default=0, ge=0, le=7)


class OutfitCreate(OutfitBase, SPECIALOutfitCreate):
    pass


class OutfitRead(OutfitBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


class OutfitUpdate(ItemUpdate):
    outfit_type: OutfitType | None = None
    gender: Gender | None = None
