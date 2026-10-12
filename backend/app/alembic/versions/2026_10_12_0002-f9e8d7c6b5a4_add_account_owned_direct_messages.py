"""add account-owned direct messages

Revision ID: f9e8d7c6b5a4
Revises: c8b2d4e6f8a1
Create Date: 2026-10-12 00:02:00.000000

Step 2 of the social slice (B1): ``directmessage`` stores consent-gated
account-to-account messages with NO ``vault_id`` (dweller chat stays
untouched). ``is_request`` records the unanswered consent gate; ``read_at``
stays internal (no read-receipt surface is exposed).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9e8d7c6b5a4"
down_revision: str | None = "c8b2d4e6f8a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "directmessage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sender_user_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("is_request", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_directmessage_id"), "directmessage", ["id"], unique=False)
    op.create_index(op.f("ix_directmessage_sender_user_id"), "directmessage", ["sender_user_id"], unique=False)
    op.create_index(op.f("ix_directmessage_recipient_user_id"), "directmessage", ["recipient_user_id"], unique=False)
    op.create_index(op.f("ix_directmessage_is_request"), "directmessage", ["is_request"], unique=False)


def downgrade() -> None:
    op.drop_table("directmessage")
