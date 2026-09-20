"""add attack requirement type

Revision ID: e7557bf3d75d
Revises: 6cd39cf3b78d
Create Date: 2026-09-20 11:18:14.850048

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7557bf3d75d"
down_revision: str | None = "6cd39cf3b78d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # RequirementType gains ATTACK (equipped weapon average damage threshold, the real
    # game's "Attack N+" quest gates). Alembic autogenerate does not detect enum value
    # changes — see AGENTS.md "DB Enums & Alembic Migrations". The requirementtype labels
    # are stored by enum member name (uppercase).
    op.execute("ALTER TYPE requirementtype ADD VALUE IF NOT EXISTS 'ATTACK'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; no data uses ATTACK yet, so the
    # unused member is left in place (harmless) rather than recreating the type.
    pass
