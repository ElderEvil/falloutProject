"""Add RESPONSE to roomtypeenum (issue 997, response station).

Revision ID: a7d4e1f2c3b4
Revises: f6a1b2c3d4e5
Create Date: 2026-10-14 00:03:00.000000

The Python ``RoomTypeEnum`` defines ``RESPONSE`` but the PostgreSQL
``roomtypeenum`` type was created without it. Alembic autogenerate does not
detect enum value changes, so this is a manual ``ALTER TYPE ... ADD VALUE``
(see AGENTS.md "DB Enums & Alembic Migrations"). Without it, writing a room
with ``category = 'RESPONSE'`` raises ``InvalidTextRepresentationError``,
which poisons the connection pool and crash-loops the worker. ``IF NOT EXISTS``
keeps the migration idempotent.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d4e1f2c3b4"
down_revision: str | None = "f6a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE roomtypeenum ADD VALUE IF NOT EXISTS 'RESPONSE'")


def downgrade() -> None:
    # PostgreSQL has no DROP VALUE, so the label is intentionally left in place.
    # A true revert would require recreating the whole type while rewriting every
    # dependent ``room.category`` row — see 2026_08_23_0001 for the recreate
    # pattern — and is not worth the data-rewrite risk. Documented no-op.
    pass
