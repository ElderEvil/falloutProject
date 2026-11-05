"""Broadcast model for Vault Radio Hour."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, Index, String
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.vault import Vault


class BroadcastBase(SQLModel):
    """Shared broadcast fields."""

    vault_id: UUID = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    title: str = Field(max_length=255)
    script: str = Field(sa_column=Column(String(), nullable=False))
    audio_key: str | None = Field(default=None, max_length=512)
    trigger: str = Field(default="daily", max_length=20, description="daily | manual")

    def __str__(self) -> str:
        return f"Broadcast #{self.id} for vault {self.vault_id}"


class Broadcast(BaseUUIDModel, BroadcastBase, TimeStampMixin, table=True):
    """A Vault Radio Hour broadcast — script + audio clip for a vault."""

    __table_args__ = (Index("ix_broadcast_vault_id_created_at", "vault_id", "created_at"),)

    # Override TimeStampMixin.created_at to be non-nullable (matches migration)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))

    vault: "Vault" = Relationship(back_populates="broadcasts")
