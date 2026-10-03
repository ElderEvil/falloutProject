"""drop dweller is_adult

Revision ID: d4e6f8a0b2c4
Revises: f2a7926009fe
Create Date: 2026-10-04 00:00:00.000000

``is_adult`` is a denormalized mirror of ``age_group``: every writer set both in
lockstep and every gameplay gate already combined ``is_adult AND age_group IN
ADULT_AGE_GROUPS``. ``age_group`` is the source of truth (mature = ``age_group in
ADULT_AGE_GROUPS``), so the column is dropped progress-preserving — no data loss,
since the invariant ``is_adult == (age_group in ADULT_AGE_GROUPS)`` held across
all writers. ``downgrade()`` reconstructs the flag from ``age_group`` (see below).

**Deployment:** this is a breaking schema change and must run in a maintenance
window. The release workflow rolls out backend/worker before migrations, and the
old code both selects and writes a NOT NULL ``is_adult`` with no default, so a
rolling deploy would fail to create dwellers in the gap (and dropping the column
before old pods stop is equally unsafe). Stop API and worker, run this migration,
then start the new release. Reproducible rollout/recovery is tracked in #885.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e6f8a0b2c4"
down_revision: str | None = "f2a7926009fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reconstruct the pre-drop invariant for existing rows on rollback: only ADULT and
# ELDER were ``is_adult``. A bare ``server_default=true`` would wrongly mark every
# CHILD/TEEN row as an adult, which old code reads via ``~is_adult`` to find
# apprenticeship candidates.
BACKFILL_IS_ADULT = sa.text(
    "UPDATE dweller SET is_adult = (CAST(age_group AS TEXT) IN ('ADULT', 'ELDER'))"
)


def upgrade() -> None:
    op.drop_column("dweller", "is_adult")


def downgrade() -> None:
    op.add_column("dweller", sa.Column("is_adult", sa.Boolean(), nullable=True))
    op.execute(BACKFILL_IS_ADULT)
    op.alter_column("dweller", "is_adult", nullable=False, server_default=sa.text("true"))
