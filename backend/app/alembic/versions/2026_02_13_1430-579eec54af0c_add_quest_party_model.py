"""add quest party model

Revision ID: 579eec54af0c
Revises: 3d3a9385bae4
Create Date: 2026-02-13 14:30:21.153318

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "579eec54af0c"
down_revision: Union[str, None] = "3d3a9385bae4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quest_party",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("slot_number", sa.Integer(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("dweller_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quest_id"], ["quest.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quest_id", "vault_id", "dweller_id", name="uq_quest_dweller"),
        sa.UniqueConstraint("quest_id", "vault_id", "slot_number", name="uq_quest_slot"),
    )
    op.create_index(op.f("ix_quest_party_dweller_id"), "quest_party", ["dweller_id"], unique=False)
    op.create_index(op.f("ix_quest_party_id"), "quest_party", ["id"], unique=False)
    op.create_index(op.f("ix_quest_party_quest_id"), "quest_party", ["quest_id"], unique=False)
    op.create_index(op.f("ix_quest_party_vault_id"), "quest_party", ["vault_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quest_party_vault_id"), table_name="quest_party")
    op.drop_index(op.f("ix_quest_party_quest_id"), table_name="quest_party")
    op.drop_index(op.f("ix_quest_party_id"), table_name="quest_party")
    op.drop_index(op.f("ix_quest_party_dweller_id"), table_name="quest_party")
    op.drop_table("quest_party")
