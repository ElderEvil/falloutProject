"""add quest duration and started_at

Revision ID: 88c95b8e064f
Revises: a209e58a23bd
Create Date: 2026-02-13 15:48:47.812855

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "88c95b8e064f"
down_revision: Union[str, None] = "a209e58a23bd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("quest", sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="60"))
    op.add_column("vaultquestcompletionlink", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("vaultquestcompletionlink", sa.Column("duration_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("vaultquestcompletionlink", "duration_minutes")
    op.drop_column("vaultquestcompletionlink", "started_at")
    op.drop_column("quest", "duration_minutes")
