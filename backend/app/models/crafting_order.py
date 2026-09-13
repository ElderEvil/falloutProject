"""Crafting orders — the workshop queue that replaces instant crafting."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.core.enums import RarityEnum
from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.room import Room
    from app.models.vault import Vault


class CraftingOrderStatus(StrEnum):
    """Lifecycle of a workshop order."""

    ACTIVE = "active"
    COMPLETED = "completed"
    COLLECTED = "collected"


class CraftingOrderBase(SQLModel):
    vault_id: UUID4 = Field(foreign_key="vault.id", index=True)
    room_id: UUID4 = Field(foreign_key="room.id", index=True)

    item_name: str = Field(min_length=3, max_length=64)
    # Catalog category ("weapon" | "outfit"); validated by the service so the
    # table needs no PostgreSQL enum type.
    item_type: str = Field(max_length=16)
    rarity: RarityEnum

    status: CraftingOrderStatus = Field(default=CraftingOrderStatus.ACTIVE, index=True)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)

    started_at: datetime
    estimated_completion_at: datetime
    completed_at: datetime | None = Field(default=None)

    # Materials the order already consumed, kept for display and auditing.
    junk_spent: int = Field(default=0, ge=0)
    caps_spent: int = Field(default=0, ge=0)
    workers_at_start: int = Field(default=0, ge=0)

    def is_active(self) -> bool:
        return self.status == CraftingOrderStatus.ACTIVE

    def is_completed(self) -> bool:
        return self.status == CraftingOrderStatus.COMPLETED

    def is_collected(self) -> bool:
        return self.status == CraftingOrderStatus.COLLECTED

    def time_remaining_seconds(self) -> int:
        """Seconds until completion, or 0 once it is no longer active."""
        if not self.is_active():
            return 0
        return max(0, int((self.estimated_completion_at - datetime.utcnow()).total_seconds()))


class CraftingOrder(BaseUUIDModel, CraftingOrderBase, TimeStampMixin, table=True):
    """One queued craft at a workshop."""

    vault: "Vault" = Relationship()
    room: "Room" = Relationship()

    def __str__(self):
        return f"{self.item_name} ({self.status})"
