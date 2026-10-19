"""Combat Zone state: one party row per vault, live matches, and the match journal.

The party row is reused across sends (``HOME`` between fights) so a vault never
accumulates history rows. A match references two party rows, never vaults: the
escrow lives on the party, and the winner is the party row that still carries it.
Matches are resolved by the dedicated 2 s actor (``api/combat_zone_tasks.py``),
not by the vault tick.
"""

from datetime import datetime

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field

from app.core.enums import CombatZoneMatchStatus, CombatZonePartyStatus, CombatZoneStance
from app.models.base import BaseUUIDModel, TimeStampMixin


class CombatZoneParty(BaseUUIDModel, TimeStampMixin, table=True):
    """A vault's single Combat Zone party and its lifecycle position.

    ``dweller_id`` is the party in v1 (1v1 encounters). ``origin_room_id`` lets a
    returned worker go back to the room they left; it is captured at send time and
    cleared when the return is finalized.
    """

    __tablename__ = "combat_zone_party"
    __table_args__ = (
        sa.UniqueConstraint("vault_id", name="uq_combat_zone_party_vault"),
        sa.CheckConstraint("escrow_caps >= 0", name="ck_combat_zone_party_escrow_non_negative"),
    )

    vault_id: UUID4 = Field(foreign_key="vault.id", ondelete="CASCADE", index=True)
    dweller_id: UUID4 = Field(foreign_key="dweller.id", ondelete="CASCADE", index=True)
    origin_room_id: UUID4 | None = Field(default=None, foreign_key="room.id", ondelete="SET NULL")
    status: CombatZonePartyStatus = Field(
        default=CombatZonePartyStatus.HOME,
        sa_column=sa.Column(
            sa.Enum(CombatZonePartyStatus, name="combatzonepartystatus"),
            nullable=False,
            server_default=CombatZonePartyStatus.HOME.name,
            index=True,
        ),
    )
    stance: CombatZoneStance = Field(
        default=CombatZoneStance.DEFENSIVE,
        sa_column=sa.Column(
            sa.Enum(CombatZoneStance, name="combatzonestance"),
            nullable=False,
            server_default=CombatZoneStance.DEFENSIVE.name,
        ),
    )
    stance_updated_at: datetime = Field(default_factory=datetime.utcnow)
    arrives_at: datetime | None = Field(default=None)
    escrow_caps: int = Field(default=0, ge=0)


class CombatZoneMatch(BaseUUIDModel, TimeStampMixin, table=True):
    """A live or finished 1v1 match. ``next_attack_party`` alternates A/B each round."""

    __tablename__ = "combat_zone_match"
    __table_args__ = (
        sa.CheckConstraint("party_a_id <> party_b_id", name="ck_combat_zone_match_distinct_parties"),
        sa.CheckConstraint("round_seq >= 1", name="ck_combat_zone_match_round_positive"),
        sa.CheckConstraint("pot_caps >= 0", name="ck_combat_zone_match_pot_non_negative"),
    )

    party_a_id: UUID4 = Field(foreign_key="combat_zone_party.id", ondelete="CASCADE", index=True)
    party_b_id: UUID4 = Field(foreign_key="combat_zone_party.id", ondelete="CASCADE", index=True)
    # Participant snapshot: the party row is reused on the next send, so a finished
    # match must not read its history through the party's current dweller.
    party_a_dweller_id: UUID4 | None = Field(default=None, foreign_key="dweller.id", ondelete="SET NULL", index=True)
    party_b_dweller_id: UUID4 | None = Field(default=None, foreign_key="dweller.id", ondelete="SET NULL", index=True)
    party_a_name: str = Field(max_length=64)
    party_b_name: str = Field(max_length=64)
    party_a_vault_number: int
    party_b_vault_number: int
    status: CombatZoneMatchStatus = Field(
        default=CombatZoneMatchStatus.ACTIVE,
        sa_column=sa.Column(
            sa.Enum(CombatZoneMatchStatus, name="combatzonematchstatus"),
            nullable=False,
            server_default=CombatZoneMatchStatus.ACTIVE.name,
            index=True,
        ),
    )
    next_attack_party: str = Field(default="A", sa_column=sa.Column(sa.String(1), nullable=False, server_default="A"))
    round_seq: int = Field(default=1, ge=1)
    pot_caps: int = Field(default=0, ge=0)
    winner_party_id: UUID4 | None = Field(default=None, foreign_key="combat_zone_party.id", ondelete="SET NULL")
    finish_reason: str | None = Field(default=None, max_length=32)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    max_ends_at: datetime | None = Field(default=None)


class CombatZoneEvent(BaseUUIDModel, TimeStampMixin, table=True):
    """Append-only match journal; clients poll after the last seen ``round_seq``."""

    __tablename__ = "combat_zone_event"

    match_id: UUID4 = Field(foreign_key="combat_zone_match.id", ondelete="CASCADE", index=True)
    round_seq: int = Field(default=1, ge=1)
    kind: str = Field(max_length=16, index=True)
    message: str = Field(max_length=200)
