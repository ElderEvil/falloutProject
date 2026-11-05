"""Broadcast model for Vault Radio Hour."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.vault import Vault


class BroadcastBase(SQLModel):
    """Shared broadcast fields."""

    vault_id: UUID = Field(foreign_key="vault.id", index=True)
    title: str = Field(max_length=255)
    script: str = Field(sa_column=String())  # text column
    audio_key: str | None = Field(default=None, max_length=512)
    trigger: str = Field(
        default="daily",
        sa_column=Field(default="daily", sa_type=String(20)),
        description="daily | manual",
    )

    def __str__(self) -> str:
        return f"Broadcast #{self.id} for vault {self.vault_id}"


class Broadcast(BaseUUIDModel, BroadcastBase, TimeStampMixin, table=True):
    """A Vault Radio Hour broadcast — script + audio clip for a vault."""

    vault: "Vault" = Relationship(back_populates="broadcasts")
