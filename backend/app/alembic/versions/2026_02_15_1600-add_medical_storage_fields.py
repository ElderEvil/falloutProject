"""add medical storage fields to vault

Revision ID: add_medical_storage_fields
Revises: 88c95b8e064f
Create Date: 2026-02-15 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "add_medical_storage_fields"
down_revision: Union[str, None] = "88c95b8e064f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vault", sa.Column("stimpack", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vault", sa.Column("stimpack_max", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vault", sa.Column("radaway", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vault", sa.Column("radaway_max", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("vault", "radaway_max")
    op.drop_column("vault", "radaway")
    op.drop_column("vault", "stimpack_max")
    op.drop_column("vault", "stimpack")
