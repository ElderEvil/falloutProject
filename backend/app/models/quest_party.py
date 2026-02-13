"""Quest party model for tracking dwellers assigned to quests."""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.quest import Quest
    from app.models.vault import Vault


class QuestPartyBase(SQLModel):
    """Base model for quest party assignments."""

    slot_number: int = Field(ge=1, le=3, description="Party slot 1-3")
    status: str = Field(default="assigned", description="assigned, in_progress, completed, failed")


class QuestParty(BaseUUIDModel, QuestPartyBase, TimeStampMixin, table=True):
    """Links dwellers to quests they've been assigned to."""

    __tablename__ = "quest_party"

    quest_id: UUID4 = Field(
        foreign_key="quest.id",
        index=True,
        ondelete="CASCADE",
        description="Quest being undertaken",
    )
    vault_id: UUID4 = Field(
        foreign_key="vault.id",
        index=True,
        ondelete="CASCADE",
        description="Vault the quest belongs to",
    )
    dweller_id: UUID4 = Field(
        foreign_key="dweller.id",
        index=True,
        ondelete="CASCADE",
        description="Dweller assigned to this slot",
    )

    # Relationships
    quest: "Quest" = Relationship(back_populates="party_members")
    vault: "Vault" = Relationship(back_populates="quest_parties")
    dweller: "Dweller" = Relationship(back_populates="quest_assignments")

    # Unique constraint: one dweller per quest per vault
    __table_args__ = (
        sa.UniqueConstraint("quest_id", "vault_id", "dweller_id", name="uq_quest_dweller"),
        sa.UniqueConstraint("quest_id", "vault_id", "slot_number", name="uq_quest_slot"),
    )
