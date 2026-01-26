"""add_soft_delete_to_users_and_dwellers

Revision ID: 3a4b32b46a8b
Revises: fc75e738a303
Create Date: 2026-01-26 20:28:16.459204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '3a4b32b46a8b'
down_revision: Union[str, None] = 'fc75e738a303'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add soft delete columns to user table
    op.add_column('user', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('user', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_user_is_deleted'), 'user', ['is_deleted'], unique=False)

    # Add soft delete columns to dweller table
    op.add_column('dweller', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('dweller', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_dweller_is_deleted'), 'dweller', ['is_deleted'], unique=False)


def downgrade() -> None:
    # Remove soft delete columns from dweller table
    op.drop_index(op.f('ix_dweller_is_deleted'), table_name='dweller')
    op.drop_column('dweller', 'deleted_at')
    op.drop_column('dweller', 'is_deleted')

    # Remove soft delete columns from user table
    op.drop_index(op.f('ix_user_is_deleted'), table_name='user')
    op.drop_column('user', 'deleted_at')
    op.drop_column('user', 'is_deleted')
