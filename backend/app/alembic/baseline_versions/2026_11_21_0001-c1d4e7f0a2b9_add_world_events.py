"""add world_event and world_event_participation tables

Revision ID: c1d4e7f0a2b9
Revises: a80944c56929
Create Date: 2026-11-21 00:01:00.000000

Server-wide co-op world events: one row per event plus one participation row per
(event, vault). New PG enum ``worldeventstatus`` ships with the table; its labels are
pinned in ``PG_ENUM_LABELS_SNAPSHOT`` (test_enum_drift) in the same commit. A partial
unique index keeps at most one ACTIVE event.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d4e7f0a2b9"
down_revision: str | None = "a80944c56929"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worldevent",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column("target_amount", sa.Integer(), nullable=False),
        sa.Column("progress_amount", sa.Integer(), nullable=False),
        sa.Column("personal_min", sa.Integer(), nullable=False),
        sa.Column("reward", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("SCHEDULED", "ACTIVE", "COMPLETED", "EXPIRED", name="worldeventstatus"),
            nullable=False,
        ),
        sa.Column("extended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_worldevent_id"), "worldevent", ["id"], unique=False)
    op.create_index(op.f("ix_worldevent_kind"), "worldevent", ["kind"], unique=False)
    # Backstop against two concurrent activations: at most one ACTIVE event server-wide.
    op.create_index(
        "uq_world_event_single_active",
        "worldevent",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
        # Keep the SQLite shape identical so the fragment migration test enforces the same rule.
        sqlite_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "worldeventparticipation",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("world_event_id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("contribution", sa.Integer(), nullable=False),
        sa.Column("reward_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["world_event_id"], ["worldevent.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("world_event_id", "vault_id", name="uq_world_event_participation"),
    )
    op.create_index(
        op.f("ix_worldeventparticipation_id"), "worldeventparticipation", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_worldeventparticipation_vault_id"),
        "worldeventparticipation",
        ["vault_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worldeventparticipation_world_event_id"),
        "worldeventparticipation",
        ["world_event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_worldeventparticipation_world_event_id"), table_name="worldeventparticipation"
    )
    op.drop_index(op.f("ix_worldeventparticipation_vault_id"), table_name="worldeventparticipation")
    op.drop_index(op.f("ix_worldeventparticipation_id"), table_name="worldeventparticipation")
    op.drop_table("worldeventparticipation")

    op.drop_index("uq_world_event_single_active", table_name="worldevent")
    op.drop_index(op.f("ix_worldevent_kind"), table_name="worldevent")
    op.drop_index(op.f("ix_worldevent_id"), table_name="worldevent")
    op.drop_table("worldevent")
    sa.Enum(name="worldeventstatus").drop(op.get_bind(), checkfirst=True)
