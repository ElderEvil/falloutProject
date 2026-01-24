"""fix_negative_dweller_experience

Revision ID: 8c8003fe468d
Revises: 74d6a11adead
Create Date: 2026-01-24 18:58:33.475545

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "8c8003fe468d"
down_revision: Union[str, None] = "74d6a11adead"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix existing negative experience values
    op.execute("UPDATE dweller SET experience = 0 WHERE experience < 0")

    # Add check constraint to prevent negative experience
    op.create_check_constraint("dweller_experience_positive", "dweller", "experience >= 0")


def downgrade() -> None:
    # Remove check constraint
    op.drop_constraint("dweller_experience_positive", "dweller", type_="check")
