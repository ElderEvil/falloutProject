"""add_quest_objectives_v2_10_0

Revision ID: 2675b30246ad
Revises: bf9e549247e6
Create Date: 2026-02-09 12:06:59.696344

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2675b30246ad"
down_revision: Union[str, None] = "bf9e549247e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create quest_requirement table
    op.create_table(
        "questrequirement",
        sa.Column(
            "requirement_type",
            sa.Enum("LEVEL", "ITEM", "ROOM", "DWELLER_COUNT", "QUEST_COMPLETED", name="requirementtype"),
            nullable=False,
        ),
        sa.Column("requirement_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["quest_id"], ["quest.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_questrequirement_id"), "questrequirement", ["id"], unique=False)
    op.create_index(op.f("ix_questrequirement_quest_id"), "questrequirement", ["quest_id"], unique=False)
    op.create_index(
        op.f("ix_questrequirement_requirement_type"), "questrequirement", ["requirement_type"], unique=False
    )

    # Create quest_reward table
    op.create_table(
        "questreward",
        sa.Column(
            "reward_type",
            sa.Enum("CAPS", "ITEM", "DWELLER", "RESOURCE", "EXPERIENCE", name="rewardtype"),
            nullable=False,
        ),
        sa.Column("reward_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reward_chance", sa.Float(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["quest_id"], ["quest.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_questreward_id"), "questreward", ["id"], unique=False)
    op.create_index(op.f("ix_questreward_quest_id"), "questreward", ["quest_id"], unique=False)
    op.create_index(op.f("ix_questreward_reward_type"), "questreward", ["reward_type"], unique=False)

    # Add new columns to objective table
    op.add_column("objective", sa.Column("objective_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column("objective", sa.Column("target_entity", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("objective", sa.Column("target_amount", sa.Integer(), nullable=False, server_default="1"))
    op.create_index(op.f("ix_objective_objective_type"), "objective", ["objective_type"], unique=False)

    questtype = postgresql.ENUM("MAIN", "SIDE", "DAILY", "EVENT", "REPEATABLE", name="questtype", create_type=False)
    questtype.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "quest",
        sa.Column(
            "quest_type",
            questtype,
            nullable=False,
            server_default="SIDE",
        ),
    )
    op.add_column("quest", sa.Column("quest_category", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True))
    op.add_column("quest", sa.Column("chain_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True))
    op.add_column("quest", sa.Column("chain_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("quest", sa.Column("previous_quest_id", sa.UUID(), nullable=True))
    op.add_column("quest", sa.Column("next_quest_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_quest_chain_id"), "quest", ["chain_id"], unique=False)
    op.create_index(op.f("ix_quest_quest_category"), "quest", ["quest_category"], unique=False)
    op.create_index(op.f("ix_quest_quest_type"), "quest", ["quest_type"], unique=False)
    op.create_foreign_key(
        "fk_quest_previous_quest_id", "quest", "quest", ["previous_quest_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key("fk_quest_next_quest_id", "quest", "quest", ["next_quest_id"], ["id"], ondelete="SET NULL")

    # Remove server defaults after backfilling existing rows
    op.alter_column("objective", "target_amount", server_default=None)
    op.alter_column("quest", "quest_type", server_default=None)
    op.alter_column("quest", "chain_order", server_default=None)


def downgrade() -> None:
    # Drop quest self-referential foreign keys
    op.drop_constraint("fk_quest_next_quest_id", "quest", type_="foreignkey")
    op.drop_constraint("fk_quest_previous_quest_id", "quest", type_="foreignkey")

    # Drop quest new indexes and columns
    op.drop_index(op.f("ix_quest_quest_type"), table_name="quest")
    op.drop_index(op.f("ix_quest_quest_category"), table_name="quest")
    op.drop_index(op.f("ix_quest_chain_id"), table_name="quest")
    op.drop_column("quest", "next_quest_id")
    op.drop_column("quest", "previous_quest_id")
    op.drop_column("quest", "chain_order")
    op.drop_column("quest", "chain_id")
    op.drop_column("quest", "quest_category")
    op.drop_column("quest", "quest_type")

    # Drop objective new indexes and columns
    op.drop_index(op.f("ix_objective_objective_type"), table_name="objective")
    op.drop_column("objective", "target_amount")
    op.drop_column("objective", "target_entity")
    op.drop_column("objective", "objective_type")

    # Drop new tables
    op.drop_index(op.f("ix_questreward_reward_type"), table_name="questreward")
    op.drop_index(op.f("ix_questreward_quest_id"), table_name="questreward")
    op.drop_index(op.f("ix_questreward_id"), table_name="questreward")
    op.drop_table("questreward")
    op.drop_index(op.f("ix_questrequirement_requirement_type"), table_name="questrequirement")
    op.drop_index(op.f("ix_questrequirement_quest_id"), table_name="questrequirement")
    op.drop_index(op.f("ix_questrequirement_id"), table_name="questrequirement")
    op.drop_table("questrequirement")

    # Drop enum types
    sa.Enum(name="questtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="requirementtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="rewardtype").drop(op.get_bind(), checkfirst=True)
