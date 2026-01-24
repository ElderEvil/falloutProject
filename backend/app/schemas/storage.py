"""Storage schemas for API responses."""

from pydantic import BaseModel, Field


class StorageSpaceResponse(BaseModel):
    """Storage space information response."""

    used_space: int = Field(..., ge=0, description="Current number of items in storage")
    max_space: int = Field(..., ge=0, description="Maximum storage capacity")
    available_space: int = Field(..., ge=0, description="Available space for new items")
    utilization_pct: float = Field(..., ge=0, le=100, description="Storage utilization percentage")

    model_config = {"from_attributes": True}
