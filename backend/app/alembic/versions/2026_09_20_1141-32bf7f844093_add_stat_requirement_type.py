"""add stat requirement type

Revision ID: 32bf7f844093
Revises: e7557bf3d75d
Create Date: 2026-09-20 11:41:50.537185

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "32bf7f844093"
down_revision: str | None = "e7557bf3d75d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # RequirementType gains STAT (minimum SPECIAL stat, the real game's "6 Strength"
    # quest gates). Alembic autogenerate does not detect enum value changes — see
    # AGENTS.md "DB Enums & Alembic Migrations". Labels are stored by member name.
    op.execute("ALTER TYPE requirementtype ADD VALUE IF NOT EXISTS 'STAT'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; no data uses STAT yet, so the
    # unused member is left in place (harmless) rather than recreating the type.
    pass
