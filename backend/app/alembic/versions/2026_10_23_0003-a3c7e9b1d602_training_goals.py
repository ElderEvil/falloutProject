"""Persist individual goals across repeated training rounds.

Revision ID: a3c7e9b1d602
Revises: f2a7c9d4e810
"""

import sqlalchemy as sa
from alembic import op

revision = "a3c7e9b1d602"
down_revision = "f2a7c9d4e810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 10 is correct for existing chains: continuous training previously always
    # repeated to 10. Backfill explicitly before enforcing the invariant.
    op.add_column("training", sa.Column("goal_stat_value", sa.Integer(), nullable=True))
    op.execute("UPDATE training SET goal_stat_value = 10 WHERE goal_stat_value IS NULL")
    with op.batch_alter_table("training") as batch_op:
        batch_op.alter_column("goal_stat_value", existing_type=sa.Integer(), nullable=False, server_default="10")
        batch_op.create_check_constraint("ck_training_goal_range", "goal_stat_value BETWEEN 2 AND 10")


def downgrade() -> None:
    with op.batch_alter_table("training") as batch_op:
        batch_op.drop_constraint("ck_training_goal_range", type_="check")
        batch_op.drop_column("goal_stat_value")
