"""fix_exploration_dweller_fk_cascade

Revision ID: 8db3164d3ed7
Revises: 3f6b056a8b94
Create Date: 2025-12-30 11:50:42.594564

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '8db3164d3ed7'
down_revision: Union[str, None] = '3f6b056a8b94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing foreign key constraint
    op.drop_constraint('exploration_dweller_id_fkey', 'exploration', type_='foreignkey')

    # Recreate it with CASCADE on delete
    op.create_foreign_key(
        'exploration_dweller_id_fkey',
        'exploration',
        'dweller',
        ['dweller_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Drop the CASCADE foreign key
    op.drop_constraint('exploration_dweller_id_fkey', 'exploration', type_='foreignkey')

    # Recreate the original constraint without CASCADE
    op.create_foreign_key(
        'exploration_dweller_id_fkey',
        'exploration',
        'dweller',
        ['dweller_id'],
        ['id']
    )
