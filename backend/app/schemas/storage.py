"""Storage schemas for API responses."""

from pydantic import BaseModel, Field

from app.schemas.junk import JunkRead
from app.schemas.outfit import OutfitRead
from app.schemas.weapon import WeaponRead


class StorageSpaceResponse(BaseModel):
    """Storage space information response."""

    used_space: int = Field(..., ge=0, description="Current number of items in storage")
    max_space: int = Field(..., ge=0, description="Maximum storage capacity")
    available_space: int = Field(..., ge=0, description="Available space for new items")
    utilization_pct: float = Field(..., ge=0, le=100, description="Storage utilization percentage")

    model_config = {"from_attributes": True}


class StorageItemsResponse(BaseModel):
    """Storage items response with all item types."""

    weapons: list[WeaponRead] = Field(default_factory=list, description="Weapons in storage")
    outfits: list[OutfitRead] = Field(default_factory=list, description="Outfits in storage")
    junk: list[JunkRead] = Field(default_factory=list, description="Junk items in storage")

    model_config = {"from_attributes": True}
