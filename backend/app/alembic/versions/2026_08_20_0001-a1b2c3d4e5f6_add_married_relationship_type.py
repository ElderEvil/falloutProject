"""add_married_relationship_type

Revision ID: a1b2c3d4e5f6
Revises: 5c88a7e4d918
Create Date: 2026-08-20 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "5c88a7e4d918"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The Python RelationshipTypeEnum defines MARRIED but the PostgreSQL
    # relationshiptypeenum type was created without it. Without this migration,
    # writing a MARRIED relationship raises InvalidTextRepresentationError:
    #   invalid input value for enum relationshiptypeenum: "MARRIED"
    # See AGENTS.md "DB Enums & Alembic Migrations" (manual ALTER TYPE required;
    # autogenerate does not detect enum value changes).
    op.execute("ALTER TYPE relationshiptypeenum ADD VALUE 'MARRIED'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing a single value from an enum.
    # Rename back to the lowercase form so the value still exists (no DROP VALUE).
    # A full revert would require recreating the type (see AGENTS.md).
    op.execute("ALTER TYPE relationshiptypeenum RENAME VALUE 'MARRIED' TO 'married'")