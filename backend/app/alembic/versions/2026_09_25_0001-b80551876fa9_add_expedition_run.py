"""add expedition_run table for interactive expedition sites

Revision ID: b80551876fa9
Revises: f4e5d6c7b8a9
Create Date: 2026-09-25 00:01:00.000000

One row per site attempt: room cursor, open/finished status, flags, and the
finished_at timestamp backing the 7-day per-vault anti-farm rule. Partial
unique indexes limit open runs by exploration and vault/site. New PG enum
``expeditionrunstatus`` ships with the table; its labels are pinned in
``PG_ENUM_LABELS_SNAPSHOT`` (test_enum_drift) in the same commit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b80551876fa9"
down_revision: str | None = "f4e5d6c7b8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expeditionrun",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("exploration_id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("dweller_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("room_cursor", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ENTERED", "IN_ROOM", "RETREATED", "CLEARED", "DIED", name="expeditionrunstatus"),
            nullable=False,
        ),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exploration_id"], ["exploration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expeditionrun_id"), "expeditionrun", ["id"], unique=False)
    op.create_index(op.f("ix_expeditionrun_exploration_id"), "expeditionrun", ["exploration_id"], unique=False)
    # Backstop against concurrent entries: at most one open run per exploration.
    op.create_index(
        "uq_expeditionrun_open_exploration",
        "expeditionrun",
        ["exploration_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ENTERED', 'IN_ROOM')"),
    )
    op.create_index(
        "uq_expeditionrun_open_vault_site",
        "expeditionrun",
        ["vault_id", "site_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ENTERED', 'IN_ROOM')"),
    )
    op.create_index(op.f("ix_expeditionrun_vault_id"), "expeditionrun", ["vault_id"], unique=False)
    op.create_index(op.f("ix_expeditionrun_dweller_id"), "expeditionrun", ["dweller_id"], unique=False)
    op.create_index(op.f("ix_expeditionrun_site_id"), "expeditionrun", ["site_id"], unique=False)
    op.create_index(op.f("ix_expeditionrun_status"), "expeditionrun", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("expeditionrun")
    sa.Enum(name="expeditionrunstatus").drop(op.get_bind(), checkfirst=True)
