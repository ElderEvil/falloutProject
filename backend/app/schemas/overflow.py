"""Schemas for resolving loot a full vault had to hold back."""

from sqlmodel import Field, SQLModel


class OverflowActionRequest(SQLModel):
    """Resolve one held item by its index in the owner's unclaimed loot list."""

    index: int = Field(ge=0, description="Position in the unclaimed loot list")


class OverflowActionResponse(SQLModel):
    """Remaining held loot after a take or sell."""

    caps_granted: int = Field(default=0, ge=0, description="Caps granted (sell only)")
    unclaimed_loot: list[dict] = Field(default_factory=list, description="Remaining unclaimed loot")
