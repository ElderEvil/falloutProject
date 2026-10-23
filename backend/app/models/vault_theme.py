"""Per-vault room-theme ownership.

The Theme workshop crafts each theme once; a completed order grants the vault
permanent ownership, stored here as ``crafted_at``. Applying a theme requires
that row (except the always-available standard style). Boosted vaults are seeded
with every theme already crafted.
"""

from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel


class VaultTheme(SQLModel, table=True):
    """One vault's ownership of a single room theme."""

    __tablename__ = "vault_theme"

    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True, ondelete="CASCADE")
    style: str = Field(primary_key=True, max_length=16)
    crafted_at: datetime | None = Field(default=None)
    source: str = Field(default="craft", max_length=16)

    def is_crafted(self) -> bool:
        return self.crafted_at is not None
