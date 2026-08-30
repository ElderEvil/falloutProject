from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, SoftDeleteMixin, SPECIALModel, TimeStampMixin
from app.schemas.common import (
    AgeGroupEnum,
    DeathCauseEnum,
    DwellerStatusEnum,
    GenderEnum,
    RarityEnum,
    SPECIALEnum,
    WeaponTypeEnum,
)

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.outfit import Outfit
    from app.models.quest_party import QuestParty
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

    @property
    def is_mature(self) -> bool:
        """Adult by both flags — children and teens can't take combat assignments."""
        return self.is_adult and self.age_group == AgeGroupEnum.ADULT

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

    # Death system
    is_dead: bool = Field(default=False, index=True)
    death_timestamp: datetime | None = Field(default=None)
    death_cause: DeathCauseEnum | None = Field(default=None)
    is_permanently_dead: bool = Field(default=False, index=True)
    epitaph: str | None = Field(default=None, max_length=255)

    # TBD


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
        from app.core.game_config import game_config
        from app.services.leveling_service import leveling_service

        if self.level >= game_config.leveling.max_level:
            return self.current_level_xp  # Already at max

        return leveling_service.calculate_xp_required(self.level + 1)

    @property
    def xp_progress_percentage(self) -> float:
        """Calculate progress to next level as percentage (0-100)."""
        from app.core.game_config import game_config

        if self.level >= game_config.leveling.max_level:
            return 100.0

        current_xp_in_level = self.experience - self.current_level_xp
        xp_required_for_level = self.next_level_xp - self.current_level_xp

        if xp_required_for_level <= 0:
            return 0.0

        return min(100.0, (current_xp_in_level / xp_required_for_level) * 100)


class Dweller(BaseUUIDModel, DwellerBase, TimeStampMixin, SoftDeleteMixin, table=True):
    __table_args__ = (
        sa.Index(
            "uq_dweller_active_apprentice_room",
            "room_id",
            unique=True,
            postgresql_where=sa.text("apprentice_started_at IS NOT NULL AND is_deleted = false"),
            sqlite_where=sa.text("apprentice_started_at IS NOT NULL AND is_deleted = false"),
        ),
    )

    vault_id: UUID4 = Field(default=None, foreign_key="vault.id", ondelete="CASCADE", index=True)
    vault: "Vault" = Relationship(back_populates="dwellers")

    room_id: UUID4 = Field(default=None, foreign_key="room.id", nullable=True, ondelete="SET NULL", index=True)
    room: "Room" = Relationship(
        back_populates="dwellers",
        sa_relationship_kwargs={"foreign_keys": "Dweller.room_id"},
    )

    # Youth apprenticeship in a production room.
    apprentice_stat: SPECIALEnum | None = Field(default=None)
    apprentice_started_at: datetime | None = Field(default=None)
    apprentice_stat_gains: dict[str, int] = Field(
        default_factory=dict,
        sa_column=sa.Column(sa.JSON, nullable=False, server_default=sa.text("'{}'")),
    )

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

    @property
    def weapon_type(self) -> WeaponTypeEnum | None:
        weapon = self.__dict__.get("weapon")
        return weapon.weapon_type if weapon is not None else None

    @property
    def combat_power(self) -> float:
        from app.core.game_config import game_config

        weapon = self.__dict__.get("weapon")
        weapon_type = weapon.weapon_type.value if weapon is not None else "unarmed"
        weights = (
            game_config.combat.weapon_stat_weights.get(weapon_type) or game_config.combat.weapon_stat_weights["unarmed"]
        )
        stat_power = sum(getattr(self, stat, 0) * w for stat, w in weights.items())
        weapon_damage = (weapon.damage_min + weapon.damage_max) / 2 if weapon is not None else 0.0
        level_bonus = self.level * game_config.combat.level_bonus_multiplier
        return float(stat_power + weapon_damage + level_bonus)

    # Training
    trainings: list["Training"] = Relationship(back_populates="dweller", cascade_delete=True)

    sent_notifications: list["Notification"] = Relationship(
        back_populates="from_dweller",
        sa_relationship_kwargs={"foreign_keys": "[Notification.from_dweller_id]"},
    )
    quest_assignments: list["QuestParty"] = Relationship(
        back_populates="dweller",
        sa_relationship_kwargs={"cascade": "all"},
    )
