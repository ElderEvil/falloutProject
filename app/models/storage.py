from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models.junk import Junk
    from app.models.outfit import Outfit
    from app.models.vault import Vault
    from app.models.weapon import Weapon


class StorageBase(SQLModel):
    used_space: int = Field(default=0, ge=0, le=1_000)
    max_space: int = Field(default=0, ge=0, le=1_000)


class Storage(BaseUUIDModel, StorageBase, table=True):
    vault_id: UUID4 = Field(default=None, foreign_key="vault.id")
    vault: "Vault" = Relationship(back_populates="storage", sa_relationship_kwargs={"uselist": False})

    junk_items: list["Junk"] = Relationship(back_populates="storage")
    outfits: list["Outfit"] = Relationship(back_populates="storage")
    weapons: list["Weapon"] = Relationship(back_populates="storage")

    def __str__(self):
        return f"Storage of Vault {self.vault_id}"
