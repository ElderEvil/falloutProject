"""drop dweller is_adult

Revision ID: 8a7c07e1b448
Revises: f2a7926009fe
Create Date: 2026-10-04 00:00:00.000000

``is_adult`` duplicated ``age_group``: every gate reads maturity from
``age_group in ADULT_AGE_GROUPS`` and the column has no readers left, so the
drop loses no information. ``downgrade()`` reconstructs the flag from
``age_group`` (only ADULT/ELDER read back as adults).

One-time maintenance window (no rolling deploy): the release workflow starts
new code before migrating, and old code selects and writes a NOT NULL
``is_adult`` with no default, so either order fails while both versions run.
Stop API and workers, run ``alembic upgrade head``, then start the new
release. Rollback: stop workloads, run ``alembic downgrade -1``, redeploy the
previous release.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a7c07e1b448"
down_revision: str | None = "f2a7926009fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Only ADULT and ELDER were ``is_adult``. A bare ``server_default=true`` would
# wrongly mark every CHILD/TEEN row as an adult on rollback.
BACKFILL_IS_ADULT = sa.text(
    "UPDATE dweller SET is_adult = (CAST(age_group AS TEXT) IN ('ADULT', 'ELDER'))"
)


def upgrade() -> None:
    op.drop_column("dweller", "is_adult")


def downgrade() -> None:
    op.add_column("dweller", sa.Column("is_adult", sa.Boolean(), nullable=True))
    op.execute(BACKFILL_IS_ADULT)
    op.alter_column("dweller", "is_adult", nullable=False, server_default=sa.text("true"))
