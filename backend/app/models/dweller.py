from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, SPECIALModel, TimeStampMixin
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum, GenderEnum, RarityEnum

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.outfit import Outfit
    from app.models.room import Room
    from app.models.training import Training
    from app.models.vault import Vault
    from app.models.weapon import Weapon


class DwellerBaseWithoutStats(SQLModel):
    # General info
    first_name: str = Field(index=True, min_length=2, max_length=32)
    last_name: str | None = Field(default=None, index=True, max_length=32)
    is_adult: bool = True
    age_group: AgeGroupEnum = Field(default=AgeGroupEnum.ADULT)
    birth_date: datetime | None = Field(default=None)
    gender: GenderEnum = Field()
    rarity: RarityEnum = Field()

    # Backstory and appearance
    bio: str | None = Field(default=None, max_length=1024)
    visual_attributes: dict | None = Field(default=None, sa_column=sa.Column(JSONB))
    image_url: str | None = Field(default=None, max_length=255)
    thumbnail_url: str | None = Field(default=None, max_length=255)

    # Stats
    level: int = Field(default=1, ge=1, le=50)
    experience: int = Field(default=0, ge=0)
    max_health: int = Field(default=50, ge=50, le=1_500)  # Increased to allow for leveling gains
    health: int = Field(default=50, ge=0, le=1_500)
    radiation: int = Field(default=0, ge=0, le=1_000)
    happiness: int = Field(default=50, ge=10, le=100)

    # Inventory
    stimpack: int = Field(default=0, ge=0, le=15)
    radaway: int = Field(default=0, ge=0, le=15)

    # Status
    status: DwellerStatusEnum = Field(default=DwellerStatusEnum.IDLE, index=True)

    # TBD
    # job: str | None


class DwellerBase(DwellerBaseWithoutStats, SPECIALModel):
    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def current_level_xp(self) -> int:
        """Calculate total XP required for current level."""
        from app.services.leveling_service import leveling_service

        return leveling_service.calculate_xp_required(self.level)

    @property
    def next_level_xp(self) -> int:
        """Calculate total XP required for next level."""
        from app.config.game_balance import MAX_LEVEL
        from app.services.leveling_service import leveling_service

        if self.level >= MAX_LEVEL:
            return self.current_level_xp  # Already at max

        return leveling_service.calculate_xp_required(self.level + 1)

    @property
    def xp_progress_percentage(self) -> float:
        """Calculate progress to next level as percentage (0-100)."""
        from app.config.game_balance import MAX_LEVEL

        if self.level >= MAX_LEVEL:
            return 100.0

        current_xp_in_level = self.experience - self.current_level_xp
        xp_required_for_level = self.next_level_xp - self.current_level_xp

        if xp_required_for_level <= 0:
            return 0.0

        return min(100.0, (current_xp_in_level / xp_required_for_level) * 100)


class Dweller(BaseUUIDModel, DwellerBase, TimeStampMixin, table=True):
    vault_id: UUID4 = Field(default=None, foreign_key="vault.id")
    vault: "Vault" = Relationship(back_populates="dwellers")

    room_id: UUID4 = Field(default=None, foreign_key="room.id", nullable=True)
    room: "Room" = Relationship(back_populates="dwellers")

    # Relationships and Family
    partner_id: UUID4 | None = Field(
        default=None,
        sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="SET NULL"), nullable=True),
    )
    parent_1_id: UUID4 | None = Field(
        default=None,
        sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="SET NULL"), nullable=True),
    )
    parent_2_id: UUID4 | None = Field(
        default=None,
        sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="SET NULL"), nullable=True),
    )

    # Inventory
    weapon: "Weapon" = Relationship(back_populates="dweller", cascade_delete=True)
    outfit: "Outfit" = Relationship(back_populates="dweller", cascade_delete=True)

    # Training
    trainings: list["Training"] = Relationship(back_populates="dweller", cascade_delete=True)

    # Notifications sent by this dweller
    sent_notifications: list["Notification"] = Relationship(
        back_populates="from_dweller",
        sa_relationship_kwargs={"foreign_keys": "[Notification.from_dweller_id]"},
    )
