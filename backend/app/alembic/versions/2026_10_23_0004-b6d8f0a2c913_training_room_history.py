"""Preserve training history after room demolition.

Revision ID: b6d8f0a2c913
Revises: a3c7e9b1d602
"""

import sqlalchemy as sa
from alembic import op

revision = "b6d8f0a2c913"
down_revision = "a3c7e9b1d602"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("training", "room_id", existing_type=sa.Uuid(), nullable=True)
    op.drop_constraint("training_room_id_fkey", "training", type_="foreignkey")
    op.create_foreign_key("training_room_id_fkey", "training", "room", ["room_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    # Deleted rooms cannot be reconstructed. Refuse to drop their history to
    # restore the old NOT NULL column: the operator must restore those rooms first.
    if op.get_bind().execute(sa.text("SELECT 1 FROM training WHERE room_id IS NULL LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while training history references deleted rooms; restore those rooms first")
    op.drop_constraint("training_room_id_fkey", "training", type_="foreignkey")
    op.create_foreign_key("training_room_id_fkey", "training", "room", ["room_id"], ["id"])
    op.alter_column("training", "room_id", existing_type=sa.Uuid(), nullable=False)
