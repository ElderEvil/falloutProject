"""fix_training_status_enum

Revision ID: ecdc11728074
Revises: 76fb12f506f5
Create Date: 2026-01-02 14:48:25.391494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ecdc11728074'
down_revision: Union[str, None] = '76fb12f506f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the TrainingStatus enum type
    training_status_enum = sa.Enum('ACTIVE', 'COMPLETED', 'CANCELLED', name='trainingstatus', create_type=False)
    training_status_enum.create(op.get_bind(), checkfirst=True)

    # Alter the status column to use the enum type
    # First, we need to use ALTER TYPE because the column already exists as varchar
    op.execute("ALTER TABLE training ALTER COLUMN status TYPE trainingstatus USING status::trainingstatus")


def downgrade() -> None:
    # Convert back to varchar
    op.execute("ALTER TABLE training ALTER COLUMN status TYPE varchar(20)")

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS trainingstatus")
