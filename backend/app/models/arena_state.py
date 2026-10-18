"""Arena match state: the per-room fighter selection, mode and match flags.

Kept out of ``Room`` so generic room read/create/update contracts stay free of
arena-only fields. One row per arena room that has been configured for a match;
``knocked_out_ids`` persists knockouts across ticks and processes.
"""

from datetime import datetime

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.enums import ArenaMode
from app.models.base import TimeStampMixin


class ArenaState(TimeStampMixin, table=True):
    __tablename__ = "arena_state"

    room_id: UUID4 = Field(foreign_key="room.id", primary_key=True, ondelete="CASCADE")
    mode: ArenaMode | None = Field(default=None)
    next_attack_team: str = Field(default="A", sa_column=sa.Column(sa.String(1), nullable=False, server_default="A"))
    fighter_a_id: UUID4 | None = Field(default=None, foreign_key="dweller.id", index=True, ondelete="SET NULL")
    fighter_b_id: UUID4 | None = Field(default=None, foreign_key="dweller.id", index=True, ondelete="SET NULL")
    fighter_c_id: UUID4 | None = Field(default=None, foreign_key="dweller.id", index=True, ondelete="SET NULL")
    fighter_d_id: UUID4 | None = Field(default=None, foreign_key="dweller.id", index=True, ondelete="SET NULL")
    opponents: list[dict] | None = Field(default=None, sa_column=sa.Column(JSONB))
    support_bots: dict[str, dict] | None = Field(default=None, sa_column=sa.Column(JSONB))
    skill_charge: dict[str, int] | None = Field(default=None, sa_column=sa.Column(JSONB))
    queued_skill_ids: list[str] | None = Field(default=None, sa_column=sa.Column(JSONB))
    last_fight_at: datetime | None = Field(default=None)
    fight_started_at: datetime | None = Field(default=None)
    knocked_out_ids: list[str] | None = Field(default=None, sa_column=sa.Column(JSONB))
