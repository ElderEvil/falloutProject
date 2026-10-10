import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class VaultSlotBase(SQLModel):
    """A vault's persisted map placement."""

    slot_index: int = Field(ge=0)
    vault_id: UUID4 = Field(foreign_key="vault.id", ondelete="CASCADE")


class VaultSlot(BaseUUIDModel, VaultSlotBase, TimeStampMixin, table=True):
    """One slot per vault: where the vault sits on the shared atlas.

    A slot is placement, not identity: ``Vault.number`` stays the global identity and a
    slot grants no ownership or capability. Slots are globally unique, so vaults are
    discoverable across the shared map.
    """

    __tablename__ = "vaultslot"

    __table_args__ = (
        sa.UniqueConstraint("slot_index", name="uq_vault_slot_index"),
        sa.UniqueConstraint("vault_id", name="uq_vault_slot_vault"),
    )
