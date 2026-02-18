from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.common import ObjectiveCategoryEnum

if TYPE_CHECKING:
    from app.models.vault import Vault


class ObjectiveBase(SQLModel):
    challenge: str = Field(min_length=3, max_length=32, index=True)
    reward: str = Field(min_length=3, max_length=32)
    category: ObjectiveCategoryEnum = Field(
        default=ObjectiveCategoryEnum.ACHIEVEMENT,
        sa_column=Column(String(50), index=True),
        description="Objective category: daily, weekly, or achievement",
    )

    # Automation fields
    objective_type: str | None = Field(
        default=None,
        index=True,
        description="Type of objective: collect, build, train, kill, assign, reach, expedition, level_up",
    )
    target_entity: dict | None = Field(
        default=None,
        sa_column=sa.Column(JSONB),
        description="What to track, e.g. {'resource_type': 'caps'} or {'room_type': 'power_plant'}",
    )
    target_amount: int = Field(
        default=1,
        ge=1,
        description="How many/much needed to complete the objective",
    )

    def __str__(self):
        return f"{self.challenge}"


class Objective(BaseUUIDModel, ObjectiveBase, table=True):
    vaults: list["Vault"] = Relationship(
        back_populates="objectives",
        link_model=VaultObjectiveProgressLink,
    )
