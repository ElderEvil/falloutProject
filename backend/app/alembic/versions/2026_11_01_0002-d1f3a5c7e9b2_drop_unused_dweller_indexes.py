"""Drop dweller indexes with no scan traffic.

The post-#1273 baseline showed these four indexes were never chosen by the
planner: first_name and last_name have no equality predicates in the hot paths,
while the two boolean flags are low-selectivity and filtered through the
vault/status indexes. Dropping them removes about 74 MB of write amplification
without changing the query surface.

PostgreSQL runs concurrent DDL inside autocommit blocks so index drops and
rebuilds never queue live tick traffic (CodeRabbit #4433927056). SQLite keeps
plain DDL for tests.

This is intentionally not a rewrite: existing bloat remains for the later
maintenance window.
"""

from alembic import op

revision: str = "d1f3a5c7e9b2"
down_revision: str | None = "b8d1e4f6a2c9"
branch_labels: str | None = None
depends_on: str | None = None

_INDEXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ix_dweller_first_name", ("first_name",)),
    ("ix_dweller_last_name", ("last_name",)),
    ("ix_dweller_is_dead", ("is_dead",)),
    ("ix_dweller_is_permanently_dead", ("is_permanently_dead",)),
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgresql():
        with op.get_context().autocommit_block():
            for index_name, _ in _INDEXES:
                op.drop_index(index_name, table_name="dweller", postgresql_concurrently=True)
    else:
        for index_name, _ in _INDEXES:
            op.drop_index(index_name, table_name="dweller")


def downgrade() -> None:
    if _is_postgresql():
        with op.get_context().autocommit_block():
            for index_name, columns in _INDEXES:
                op.create_index(
                    index_name, "dweller", list(columns), unique=False, postgresql_concurrently=True
                )
    else:
        for index_name, columns in _INDEXES:
            op.create_index(index_name, "dweller", list(columns), unique=False)
