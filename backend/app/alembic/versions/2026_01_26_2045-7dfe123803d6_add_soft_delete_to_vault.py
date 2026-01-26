"""add_soft_delete_to_vault

Revision ID: 7dfe123803d6
Revises: 3a4b32b46a8b
Create Date: 2026-01-26 20:45:50.246661

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '7dfe123803d6'
down_revision: Union[str, None] = '3a4b32b46a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add soft delete columns to vault table
    op.add_column('vault', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('vault', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_vault_is_deleted'), 'vault', ['is_deleted'], unique=False)


def downgrade() -> None:
    # Remove soft delete columns from vault table
    op.drop_index(op.f('ix_vault_is_deleted'), table_name='vault')
    op.drop_column('vault', 'deleted_at')
    op.drop_column('vault', 'is_deleted')
