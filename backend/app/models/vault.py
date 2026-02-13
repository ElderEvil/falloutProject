from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlalchemy import Column, String
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, SoftDeleteMixin, TimeStampMixin
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.vault_quest import (
    VaultQuestCompletionLink,
)

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.objective import Objective
    from app.models.quest import Quest
    from app.models.quest_party import QuestParty
    from app.models.room import Room
    from app.models.storage import Storage
    from app.models.user import User


class VaultBase(SQLModel):
    # General information
    number: int = Field(index=True, gt=0, lt=1_000)
    bottle_caps: int = Field(default=1_000, ge=0, lt=1_000_000)
    happiness: int = Field(default=50, ge=0, le=100)

    # Primary resources
    power: int = Field(1, ge=0, le=10_000)
    power_max: int = Field(0, ge=0, le=10_000)
    food: int = Field(1, ge=0, le=10_000)
    food_max: int = Field(0, ge=0, le=10_000)
    water: int = Field(1, ge=0, le=10_000)
    water_max: int = Field(0, ge=0, le=10_000)

    # Population limits
    population_max: int | None = Field(default=0, ge=0, le=200, nullable=True)

    # Radio settings
    # Store as string in database to avoid enum type issues
    radio_mode: str = Field(default="recruitment", sa_column=Column(String(50)))

    # Game state
    # game_state: GameStatusEnum = Field(default=GameStatusEnum.ACTIVE)

    def __str__(self):
        return f"Vault {self.number:03}"


class Vault(BaseUUIDModel, VaultBase, TimeStampMixin, SoftDeleteMixin, table=True):
    user_id: UUID4 = Field(default=None, foreign_key="user.id")
    user: "User" = Relationship(back_populates="vaults")

    dwellers: list["Dweller"] = Relationship(back_populates="vault", cascade_delete=True)
    rooms: list["Room"] = Relationship(back_populates="vault", cascade_delete=True)
    storage: "Storage" = Relationship(back_populates="vault", cascade_delete=True)

    quests: list["Quest"] = Relationship(
        back_populates="vaults",
        link_model=VaultQuestCompletionLink,
    )

    objectives: list["Objective"] = Relationship(
        back_populates="vaults",
        link_model=VaultObjectiveProgressLink,
    )
    quest_parties: list["QuestParty"] = Relationship(
        back_populates="vault",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
