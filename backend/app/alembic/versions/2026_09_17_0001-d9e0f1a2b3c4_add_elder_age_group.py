"""add_elder_age_group

Revision ID: d9e0f1a2b3c4
Revises: f3a4b5c6d7e8
Create Date: 2026-09-17 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Python AgeGroupEnum defines ELDER but agegroupenum was created without it.
    # Writing an ELDER row without this migration raises
    # InvalidTextRepresentationError and poisons the connection pool.
    # Alembic autogenerate does not detect enum value changes — see AGENTS.md
    # "DB Enums & Alembic Migrations".
    op.execute("ALTER TYPE agegroupenum ADD VALUE IF NOT EXISTS 'ELDER'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value, so the type is recreated.
    # Rows still holding ELDER are normalized to ADULT first.
    op.execute("ALTER TABLE dweller ALTER COLUMN age_group TYPE VARCHAR(16) USING age_group::text")
    op.execute("UPDATE dweller SET age_group = 'ADULT' WHERE age_group = 'ELDER'")
    op.execute("DROP TYPE agegroupenum")
    op.execute("CREATE TYPE agegroupenum AS ENUM ('CHILD', 'TEEN', 'ADULT')")
    op.execute("ALTER TABLE dweller ALTER COLUMN age_group TYPE agegroupenum USING age_group::agegroupenum")
