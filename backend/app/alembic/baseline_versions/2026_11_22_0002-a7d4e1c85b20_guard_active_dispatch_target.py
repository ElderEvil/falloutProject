"""guard one active dispatch per map point

Revision ID: a7d4e1c85b20
Revises: f3a9c2d7b518
Create Date: 2026-11-22 00:02:00.000000

A site accepted a second dispatch while a party was still en route: both runs resolved the same
haul and bumped clear_count. The partial unique index makes "one party en route per vault and map
point" a database guarantee; roams (target NULL) and returning runs are excluded.

Index-only DDL, so it is created concurrently on PostgreSQL and needs no maintenance window.

Existing data is expected to satisfy it. If two ACTIVE runs already target the same point for one
vault, CREATE UNIQUE INDEX fails and the migration Job aborts the rollout rather than guessing which
run owns the site. A failed concurrent build leaves an invalid index behind and PostgreSQL will not
reuse the name, so the upgrade reclaims the name first and re-fails while the duplicate rows remain.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d4e1c85b20"
down_revision: str | None = "f3a9c2d7b518"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_exploration_active_target"
INDEX_COLUMNS = ["vault_id", "target_location_id"]
ACTIVE_TARGET = sa.text("status = 'ACTIVE' AND target_location_id IS NOT NULL")


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            # A failed concurrent build leaves an invalid index that blocks its own name; dropping it
            # first makes a retry possible, while the create below still fails on duplicate rows.
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
            op.create_index(
                INDEX_NAME,
                "exploration",
                INDEX_COLUMNS,
                unique=True,
                postgresql_where=ACTIVE_TARGET,
                postgresql_concurrently=True,
            )
        return
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    op.create_index(INDEX_NAME, "exploration", INDEX_COLUMNS, unique=True, sqlite_where=ACTIVE_TARGET)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(INDEX_NAME, table_name="exploration", postgresql_concurrently=True)
        return
    op.drop_index(INDEX_NAME, table_name="exploration")
