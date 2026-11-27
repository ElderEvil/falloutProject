"""Combat Zone state: one party row per vault, live matches, and the match journal.

The party row is reused across sends (``HOME`` between fights) so a vault never
accumulates history rows. A match references two party rows, never vaults: the
escrow lives on the party, and the winner is the party row that still carries it.
Matches are resolved by the dedicated 2 s actor (``api/combat_zone_tasks.py``),
not by the vault tick.
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.core.enums import CombatZoneMatchStatus, CombatZonePartyStatus, CombatZoneStance
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.utils.time import utcnow
from app.utils.types import UTCDateTime


class CombatZoneParty(BaseUUIDModel, TimeStampMixin, table=True):
    """A vault's single Combat Zone party and its lifecycle position.

    ``dweller_id`` is the party in v1 (1v1 encounters). ``origin_room_id`` lets a
    returned worker go back to the room they left; it is captured at send time and
    cleared when the return is finalized. Permanent dweller deletion is refused in
    ``DwellerService`` while this row references the dweller; CASCADE is kept for
    whole-vault/account deletion.
    """

    __tablename__ = "combat_zone_party"
    __table_args__ = (
        sa.UniqueConstraint("vault_id", name="uq_combat_zone_party_vault"),
        sa.CheckConstraint("escrow_caps >= 0", name="ck_combat_zone_party_escrow_non_negative"),
    )

    vault_id: UUID = Field(foreign_key="vault.id", ondelete="CASCADE", index=True)
    dweller_id: UUID = Field(foreign_key="dweller.id", ondelete="CASCADE", index=True)
    origin_room_id: UUID | None = Field(default=None, foreign_key="room.id", ondelete="SET NULL")
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
    stance_updated_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)
    arrives_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    escrow_caps: int = Field(default=0, ge=0)


class CombatZoneMatch(BaseUUIDModel, TimeStampMixin, table=True):
    """A live or finished 1v1 match. ``next_attack_party`` alternates A/B each round."""

    __tablename__ = "combat_zone_match"
    __table_args__ = (
        sa.CheckConstraint("party_a_id <> party_b_id", name="ck_combat_zone_match_distinct_parties"),
        sa.CheckConstraint("round_seq >= 1", name="ck_combat_zone_match_round_positive"),
        sa.CheckConstraint("pot_caps >= 0", name="ck_combat_zone_match_pot_non_negative"),
    )

    party_a_id: UUID = Field(foreign_key="combat_zone_party.id", ondelete="CASCADE", index=True)
    party_b_id: UUID = Field(foreign_key="combat_zone_party.id", ondelete="CASCADE", index=True)
    # Participant snapshot: the party row is reused on the next send, so a finished
    # match must not read its history through the party's current dweller.
    party_a_dweller_id: UUID | None = Field(default=None, foreign_key="dweller.id", ondelete="SET NULL", index=True)
    party_b_dweller_id: UUID | None = Field(default=None, foreign_key="dweller.id", ondelete="SET NULL", index=True)
    party_a_name: str = Field(max_length=64)
    party_b_name: str = Field(max_length=64)
    party_a_vault_number: int
    party_b_vault_number: int
    party_a_level: int | None = Field(default=None)
    party_b_level: int | None = Field(default=None)
    party_a_power: float | None = Field(default=None)
    party_b_power: float | None = Field(default=None)
    party_a_age_group: str | None = Field(default=None, max_length=16)
    party_b_age_group: str | None = Field(default=None, max_length=16)
    party_a_race: str | None = Field(default=None, max_length=32)
    party_b_race: str | None = Field(default=None, max_length=32)
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
    winner_party_id: UUID | None = Field(default=None, foreign_key="combat_zone_party.id", ondelete="SET NULL")
    finish_reason: str | None = Field(default=None, max_length=32)
    party_a_health: int | None = Field(default=None)
    party_b_health: int | None = Field(default=None)
    party_a_max_health: int | None = Field(default=None)
    party_b_max_health: int | None = Field(default=None)
    party_a_credited_caps: int | None = Field(default=None)
    party_b_credited_caps: int | None = Field(default=None)
    # Terminal stance at settlement: the party row is reset/reused, so history must not read it.
    party_a_stance: str | None = Field(default=None, max_length=16)
    party_b_stance: str | None = Field(default=None, max_length=16)
    # Fractional per-fighter damage carried between micro-rounds, keyed by dweller id.
    carry: dict[str, float] | None = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))
    started_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    finished_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    max_ends_at: datetime | None = Field(default=None, sa_type=UTCDateTime)


class CombatZoneEvent(BaseUUIDModel, TimeStampMixin, table=True):
    """Append-only match journal; clients poll after the last seen ``sequence``."""

    __tablename__ = "combat_zone_event"
    __table_args__ = (sa.UniqueConstraint("match_id", "sequence", name="uq_combat_zone_event_match_sequence"),)

    match_id: UUID = Field(foreign_key="combat_zone_match.id", ondelete="CASCADE", index=True)
    sequence: int = Field(ge=1)
    round_seq: int = Field(default=1, ge=1)
    kind: str = Field(max_length=16, index=True)
    message: str = Field(max_length=200)
    action: dict[str, object] | None = Field(default=None, sa_column=sa.Column(sa.JSON, nullable=True))
