"""add_exile_death_cause_and_exit_requests

Revision ID: e7c8d9a0b1f2
Revises: d9e0f1a2b3c4
Create Date: 2026-09-17 00:00:01.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c8d9a0b1f2"
down_revision: str | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Python DeathCauseEnum defines EXILE but deathcauseenum was created without it.
    # Alembic autogenerate does not detect enum value changes — see AGENTS.md
    # "DB Enums & Alembic Migrations". Unmigrated members poison the connection pool.
    op.execute("ALTER TYPE deathcauseenum ADD VALUE IF NOT EXISTS 'EXILE'")
    op.add_column("dweller", sa.Column("exit_requested_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("dweller", "exit_requested_at")
    # PostgreSQL cannot drop a single enum value, so the type is recreated. Rows still
    # carrying EXILE are normalized to exploration (the closest existing cause).
    op.execute("ALTER TABLE dweller ALTER COLUMN death_cause TYPE VARCHAR(16) USING death_cause::text")
    op.execute("UPDATE dweller SET death_cause = 'EXPLORATION' WHERE death_cause = 'EXILE'")
    op.execute("DROP TYPE deathcauseenum")
    op.execute("CREATE TYPE deathcauseenum AS ENUM ('HEALTH', 'RADIATION', 'INCIDENT', 'EXPLORATION', 'COMBAT')")
    op.execute("ALTER TABLE dweller ALTER COLUMN death_cause TYPE deathcauseenum USING death_cause::deathcauseenum")
