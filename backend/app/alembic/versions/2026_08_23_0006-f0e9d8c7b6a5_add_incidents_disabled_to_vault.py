"""Add incidents_disabled flag to vault - suppress incident spawns/processing."""

from alembic import op

revision = "f0e9d8c7b6a5"
down_revision: str | None = "e6f5a4b3c2d1"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE vault ADD COLUMN incidents_disabled BOOLEAN NOT NULL DEFAULT FALSE")


def downgrade() -> None:
    op.execute("ALTER TABLE vault DROP COLUMN incidents_disabled")