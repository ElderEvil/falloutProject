"""add pvpduel table

Revision ID: d4c8a1f6e293
Revises: e5a1b7c9d2f3
Create Date: 2026-11-21 00:03:00.000000

Cross-vault exhibition duels. Status is plain VARCHAR on purpose: a StrEnum-backed
string needs no PostgreSQL enum type and so no ADD VALUE migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4c8a1f6e293"
down_revision: str | Sequence[str] | None = "e5a1b7c9d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pvpduel",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("challenger_vault_id", sa.Uuid(), nullable=False),
        sa.Column("defender_vault_id", sa.Uuid(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column("challenger_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("defender_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("outcome", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column("journal", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["challenger_vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["defender_vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pvpduel_id"), "pvpduel", ["id"], unique=False)
    op.create_index(op.f("ix_pvpduel_challenger_vault_id"), "pvpduel", ["challenger_vault_id"], unique=False)
    op.create_index("ix_pvpduel_status_expires_at", "pvpduel", ["status", "expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pvpduel_status_expires_at", table_name="pvpduel")
    op.drop_index(op.f("ix_pvpduel_challenger_vault_id"), table_name="pvpduel")
    op.drop_index(op.f("ix_pvpduel_id"), table_name="pvpduel")
    op.drop_table("pvpduel")
