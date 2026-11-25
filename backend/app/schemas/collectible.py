"""Read models for the durable per-vault collectible claims and their sets."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field
from sqlmodel import SQLModel


class DwellerCollectibleRead(SQLModel):
    """One collectible a dweller found, joined with its catalog entry."""

    key: str
    name: str
    stat: str
    amount: int = Field(description="Live permanent bonus the finder holds; 0 when it was cleared")
    image: str
    location: str
    found_at: datetime


class CollectibleSetProgressRead(SQLModel):
    """One defined set and this vault's progress toward its bonus."""

    set: str
    name: str
    held: int
    required: int
    active: bool
