"""fix_junk_item_values

Revision ID: 59eb893b6170
Revises: 7dfe123803d6
Create Date: 2026-01-27 20:11:09.276615

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "59eb893b6170"
down_revision: Union[str, None] = "7dfe123803d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix junk item values based on rarity."""
    # Update junk items with NULL or 0 values based on their rarity
    # COMMON: 2 caps, RARE: 50 caps, LEGENDARY: 200 caps

    conn = op.get_bind()

    # Update COMMON rarity junk
    conn.execute(
        sa.text("""
            UPDATE junk
            SET value = 2
            WHERE rarity = 'COMMON' AND (value IS NULL OR value = 0)
        """)
    )

    # Update RARE rarity junk
    conn.execute(
        sa.text("""
            UPDATE junk
            SET value = 50
            WHERE rarity = 'RARE' AND (value IS NULL OR value = 0)
        """)
    )

    # Update LEGENDARY rarity junk
    conn.execute(
        sa.text("""
            UPDATE junk
            SET value = 200
            WHERE rarity = 'LEGENDARY' AND (value IS NULL OR value = 0)
        """)
    )


def downgrade() -> None:
    """Revert junk values to NULL."""
    # This is optional - we don't need to undo value fixes
    pass
