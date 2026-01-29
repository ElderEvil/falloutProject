"""reset_all_dwellers_to_level_1

Revision ID: fbbe3712457d
Revises: 59eb893b6170
Create Date: 2026-01-29 20:43:55.903511

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "fbbe3712457d"
down_revision: Union[str, None] = "59eb893b6170"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reset only broken dwellers (negative XP or high level with 0 XP)
    op.execute("""
        UPDATE dweller
        SET level = 1, experience = 0
        WHERE experience < 0 OR (level > 1 AND experience = 0)
    """)


def downgrade() -> None:
    # No downgrade: we don't have the original level/experience values to restore
    pass
