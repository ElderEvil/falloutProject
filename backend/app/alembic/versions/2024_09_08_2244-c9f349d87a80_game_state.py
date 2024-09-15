"""game_state

Revision ID: c9f349d87a80
Revises: e0f442dfc508
Create Date: 2024-09-08 22:44:03.086149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'c9f349d87a80'
down_revision: Union[str, None] = 'e0f442dfc508'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the custom enum type first
    op.execute("CREATE TYPE gamestatusenum AS ENUM('ACTIVE', 'PAUSED')")

    # Add the column with the enum type as nullable
    op.add_column('vault', sa.Column('game_state', sa.Enum('ACTIVE', 'PAUSED', name='gamestatusenum'), nullable=True))

    # Set a default value for all existing rows
    op.execute("UPDATE vault SET 'game_state' = 'ACTIVE'")

    # Alter the column to make it non-nullable
    op.alter_column('vault', 'game_state', nullable=False)


def downgrade() -> None:
    # Drop the column first
    op.drop_column('vault', 'game_state')

    # Drop the enum type
    op.execute("DROP TYPE gamestatusenum")
