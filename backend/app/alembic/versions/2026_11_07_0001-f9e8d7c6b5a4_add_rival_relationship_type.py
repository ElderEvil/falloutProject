"""add_rival_relationship_type

Revision ID: f9e8d7c6b5a4
Revises: d9a3b2c4e5f6
Create Date: 2026-11-07 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9e8d7c6b5a4"
down_revision: str | None = "d9a3b2c4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Python defines RIVAL but PostgreSQL needs the enum label before any API
    # or tick path can persist a rivalry row (AGENTS.md: manual ALTER TYPE).
    op.execute("ALTER TYPE relationshiptypeenum ADD VALUE 'RIVAL'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value, so recreate the type without
    # RIVAL. Rival rows return to acquaintance at neutral affinity first.
    op.execute(
        "ALTER TABLE relationship ALTER COLUMN relationship_type TYPE VARCHAR(32) "
        "USING relationship_type::text"
    )
    op.execute(
        "UPDATE relationship SET relationship_type = 'ACQUAINTANCE', affinity = GREATEST(affinity, 0) "
        "WHERE relationship_type = 'RIVAL'"
    )
    op.execute("DROP TYPE relationshiptypeenum")
    op.execute(
        "CREATE TYPE relationshiptypeenum AS ENUM "
        "('ACQUAINTANCE', 'FRIEND', 'ROMANTIC', 'PARTNER', 'MARRIED', 'EX')"
    )
    op.execute(
        "ALTER TABLE relationship ALTER COLUMN relationship_type TYPE relationshiptypeenum "
        "USING relationship_type::relationshiptypeenum"
    )
