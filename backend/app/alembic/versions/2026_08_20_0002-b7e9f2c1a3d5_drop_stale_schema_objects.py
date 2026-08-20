"""drop_stale_schema_objects

Revision ID: b7e9f2c1a3d5
Revises: a1b2c3d4e5f6
Create Date: 2026-08-20 12:55:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e9f2c1a3d5"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reconcile the live schema with the current model metadata: the Dweller
    # model no longer emits the experience>=0 check constraint, and the
    # DwellerLocation model no longer declares the is_unlocked index. Both were
    # left behind by older migrations and trip `alembic check`.
    op.drop_constraint("dweller_experience_positive", "dweller", type_="check")
    op.drop_index("ix_dwellerlocation_is_unlocked", table_name="dwellerlocation")


def downgrade() -> None:
    op.create_check_constraint("dweller_experience_positive", "dweller", "experience >= 0")
    op.create_index("ix_dwellerlocation_is_unlocked", "dwellerlocation", ["is_unlocked"])
