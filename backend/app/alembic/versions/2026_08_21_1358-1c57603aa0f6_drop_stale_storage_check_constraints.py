"""Drop stale storage check constraints.

Revision ID: 1c57603aa0f6
Revises: d4e5f6a7b8c9
Create Date: 2026-08-21 13:58:56.303074

"""
from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1c57603aa0f6"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop stale storage check constraints that the model no longer emits."""
    # The Storage model validates bounds via Pydantic (ge=0, le=10_000) and no
    # longer emits DB-level check constraints; drop the leftovers from the
    # medical-supplies migration so `alembic check` passes. IF EXISTS keeps the
    # migration idempotent for databases that never received the constraints.
    op.execute("ALTER TABLE storage DROP CONSTRAINT IF EXISTS ck_storage_stimpack_bounds")
    op.execute("ALTER TABLE storage DROP CONSTRAINT IF EXISTS ck_storage_radaway_bounds")


def downgrade() -> None:
    """Restore the storage check constraints for rollback."""
    op.create_check_constraint(
        "ck_storage_stimpack_bounds", "storage", "stimpack >= 0 AND stimpack <= 10000"
    )
    op.create_check_constraint(
        "ck_storage_radaway_bounds", "storage", "radaway >= 0 AND radaway <= 10000"
    )
