"""add_training_system

Revision ID: 76fb12f506f5
Revises: c709889b3b11
Create Date: 2026-01-02 11:44:06.134890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '76fb12f506f5'
down_revision: Union[str, None] = 'c709889b3b11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create training table
    op.create_table(
        'training',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('dweller_id', sa.Uuid(), nullable=False),
        sa.Column('room_id', sa.Uuid(), nullable=False),
        sa.Column('vault_id', sa.Uuid(), nullable=False),
        sa.Column('stat_being_trained', sa.String(length=20), nullable=False),
        sa.Column('current_stat_value', sa.Integer(), nullable=False),
        sa.Column('target_stat_value', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Float(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('estimated_completion_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['dweller_id'], ['dweller.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['room_id'], ['room.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vault_id'], ['vault.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for performance
    op.create_index('ix_training_dweller_id', 'training', ['dweller_id'])
    op.create_index('ix_training_room_id', 'training', ['room_id'])
    op.create_index('ix_training_vault_id', 'training', ['vault_id'])
    op.create_index('ix_training_status', 'training', ['status'])

    # Add index on dweller.level for leveling queries
    op.create_index('ix_dweller_level', 'dweller', ['level'])


def downgrade() -> None:
    # Remove index on dweller.level
    op.drop_index('ix_dweller_level', table_name='dweller')

    # Drop indexes
    op.drop_index('ix_training_status', table_name='training')
    op.drop_index('ix_training_vault_id', table_name='training')
    op.drop_index('ix_training_room_id', table_name='training')
    op.drop_index('ix_training_dweller_id', table_name='training')

    # Drop training table
    op.drop_table('training')
