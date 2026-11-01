"""Tune dweller for high per-tick update churn.

Fillfactor 80 leaves page space for HOT updates; the per-table autovacuum
thresholds make dead tuples visible sooner than the global 10% scale factor.
Existing full pages need a separate rewrite before they can benefit from the
reserved space.
"""

from alembic import op

revision: str = "b8d1e4f6a2c9"
down_revision: str | None = "f3a9c2b7d1e4"
branch_labels: str | None = None
depends_on: str | None = None

_SETTINGS = """
ALTER TABLE dweller SET (
    fillfactor = 80,
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_vacuum_threshold = 50,
    autovacuum_analyze_scale_factor = 0.02
)
"""

_RESET = """
ALTER TABLE dweller RESET (
    fillfactor,
    autovacuum_vacuum_scale_factor,
    autovacuum_vacuum_threshold,
    autovacuum_analyze_scale_factor
)
"""


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(_SETTINGS)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(_RESET)
