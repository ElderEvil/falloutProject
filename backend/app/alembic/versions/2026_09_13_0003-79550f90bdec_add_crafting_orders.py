"""add crafting orders

Revision ID: 79550f90bdec
Revises: b2c3d4e5f6a1
Create Date: 2026-09-13 00:00:00.000000
"""

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "79550f90bdec"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "craftingorder",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("item_name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("item_type", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column(
            "rarity",
            postgresql.ENUM("COMMON", "RARE", "LEGENDARY", name="rarityenum", create_type=False),
            nullable=False,
        ),
        sa.Column("status", sa.Enum("ACTIVE", "COMPLETED", "COLLECTED", name="craftingorderstatus"), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("estimated_completion_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("junk_spent", sa.Integer(), nullable=False),
        sa.Column("caps_spent", sa.Integer(), nullable=False),
        sa.Column("required_stat", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("ability_sum_at_start", sa.Integer(), nullable=False),
        sa.Column("item_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["room.id"]),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_craftingorder_id"), "craftingorder", ["id"], unique=False)
    op.create_index(op.f("ix_craftingorder_room_id"), "craftingorder", ["room_id"], unique=False)
    op.create_index(op.f("ix_craftingorder_status"), "craftingorder", ["status"], unique=False)
    op.create_index(op.f("ix_craftingorder_vault_id"), "craftingorder", ["vault_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_craftingorder_vault_id"), table_name="craftingorder")
    op.drop_index(op.f("ix_craftingorder_status"), table_name="craftingorder")
    op.drop_index(op.f("ix_craftingorder_room_id"), table_name="craftingorder")
    op.drop_index(op.f("ix_craftingorder_id"), table_name="craftingorder")
    op.drop_table("craftingorder")
    # The status type is owned by this table; `rarityenum` is shared and stays.
    op.execute("DROP TYPE IF EXISTS craftingorderstatus")
