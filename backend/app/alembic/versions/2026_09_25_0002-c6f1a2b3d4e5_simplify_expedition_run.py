"""Simplify persisted expedition runs after the first site release.

Revision ID: c6f1a2b3d4e5
Revises: b80551876fa9

ENTERED and IN_ROOM are behaviorally identical. Existing ENTERED rows become
IN_ROOM before the enum is recreated. Exploration already owns the dweller and
cascades deletion to its site runs, so the duplicated dweller_id is removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6f1a2b3d4e5"
down_revision: str | None = "b80551876fa9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURRENT_LABELS = ("IN_ROOM", "RETREATED", "CLEARED", "DIED")
PREVIOUS_LABELS = ("ENTERED", *CURRENT_LABELS)


def _recreate_status_enum(labels: tuple[str, ...]) -> None:
    """Replace the PostgreSQL enum after all rows use labels in ``labels``."""
    op.execute("ALTER TYPE expeditionrunstatus RENAME TO expeditionrunstatus_old")
    op.execute(f"CREATE TYPE expeditionrunstatus AS ENUM ({', '.join(repr(label) for label in labels)})")
    op.execute(
        "ALTER TABLE expeditionrun ALTER COLUMN status TYPE expeditionrunstatus "
        "USING status::text::expeditionrunstatus"
    )
    op.execute("DROP TYPE expeditionrunstatus_old")


def _drop_status_indexes() -> None:
    op.drop_index("uq_expeditionrun_open_exploration", table_name="expeditionrun")
    op.drop_index("uq_expeditionrun_open_vault_site", table_name="expeditionrun")
    op.drop_index("ix_expeditionrun_status", table_name="expeditionrun")


def _create_status_indexes(open_predicate: str) -> None:
    op.create_index("ix_expeditionrun_status", "expeditionrun", ["status"])
    op.create_index(
        "uq_expeditionrun_open_exploration",
        "expeditionrun",
        ["exploration_id"],
        unique=True,
        postgresql_where=sa.text(open_predicate),
    )
    op.create_index(
        "uq_expeditionrun_open_vault_site",
        "expeditionrun",
        ["vault_id", "site_id"],
        unique=True,
        postgresql_where=sa.text(open_predicate),
    )


def upgrade() -> None:
    op.execute("UPDATE expeditionrun SET status = 'IN_ROOM' WHERE status = 'ENTERED'")
    _drop_status_indexes()
    op.drop_index("ix_expeditionrun_dweller_id", table_name="expeditionrun")
    op.drop_column("expeditionrun", "dweller_id")
    _recreate_status_enum(CURRENT_LABELS)
    _create_status_indexes("status = 'IN_ROOM'")


def downgrade() -> None:
    _drop_status_indexes()
    _recreate_status_enum(PREVIOUS_LABELS)
    op.add_column("expeditionrun", sa.Column("dweller_id", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE expeditionrun AS run SET dweller_id = exploration.dweller_id "
        "FROM exploration WHERE run.exploration_id = exploration.id"
    )
    op.alter_column("expeditionrun", "dweller_id", nullable=False)
    op.create_foreign_key(
        "fk_expeditionrun_dweller_id_dweller", "expeditionrun", "dweller", ["dweller_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_expeditionrun_dweller_id", "expeditionrun", ["dweller_id"])
    _create_status_indexes("status IN ('ENTERED', 'IN_ROOM')")
