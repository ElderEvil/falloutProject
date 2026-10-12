"""add player connections and user blocks

Revision ID: c8b2d4e6f8a1
Revises: 862c04111ec1
Create Date: 2026-10-12 00:01:00.000000

Step 1 of the social slice (A1 + A2): ``connection`` holds a consented,
bidirectional player relationship with a unique constraint on the *unordered*
pair (``user_a``/``user_b`` hold the canonical sorted pair), and ``userblock``
holds the ordered (blocker, blocked) pair used for bilateral blocking.

``connectionstatus`` is a hand-written PostgreSQL enum: autogenerate does not
detect enum value changes, and ``PG_ENUM_LABELS_SNAPSHOT`` is updated in the
same commit per the repo's enum-drift procedure.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8b2d4e6f8a1"
down_revision: str | None = "862c04111ec1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The inline sa.Enum(...) in the status column creates the connectionstatus
    # PostgreSQL enum type automatically; hand-writing CREATE TYPE here would
    # attempt a duplicate creation on the same transaction.
    op.create_table(
        "connection",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("addressee_id", sa.Uuid(), nullable=False),
        sa.Column("user_a", sa.Uuid(), nullable=False),
        sa.Column("user_b", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "ACCEPTED", name="connectionstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_a", "user_b", name="uq_connection_user_pair"),
    )
    op.create_index(op.f("ix_connection_id"), "connection", ["id"], unique=False)
    op.create_index(op.f("ix_connection_requester_id"), "connection", ["requester_id"], unique=False)
    op.create_index(op.f("ix_connection_addressee_id"), "connection", ["addressee_id"], unique=False)
    op.create_index(op.f("ix_connection_status"), "connection", ["status"], unique=False)
    op.create_index(op.f("ix_connection_user_a"), "connection", ["user_a"], unique=False)
    op.create_index(op.f("ix_connection_user_b"), "connection", ["user_b"], unique=False)

    op.create_table(
        "userblock",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("blocker_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_userblock_blocker_blocked"),
    )
    op.create_index(op.f("ix_userblock_id"), "userblock", ["id"], unique=False)
    op.create_index(op.f("ix_userblock_blocker_id"), "userblock", ["blocker_id"], unique=False)
    op.create_index(op.f("ix_userblock_blocked_id"), "userblock", ["blocked_id"], unique=False)


def downgrade() -> None:
    op.drop_table("userblock")
    op.drop_table("connection")
    op.execute("DROP TYPE connectionstatus")