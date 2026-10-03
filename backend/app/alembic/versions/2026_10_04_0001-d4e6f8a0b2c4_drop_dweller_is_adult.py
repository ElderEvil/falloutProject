"""drop dweller is_adult

Revision ID: d4e6f8a0b2c4
Revises: f2a7926009fe
Create Date: 2026-10-04 00:00:00.000000

``is_adult`` is a denormalized mirror of ``age_group``: every writer set both in
lockstep and every gameplay gate already combined ``is_adult AND age_group IN
ADULT_AGE_GROUPS``. ``age_group`` is the source of truth (mature = ``age_group in
ADULT_AGE_GROUPS``), so the column is dropped progress-preserving — no data loss,
since the invariant ``is_adult == (age_group in ADULT_AGE_GROUPS)`` held across
all writers. ``downgrade()`` re-adds the column with the historical default
(``true``) so pre-existing rows read as adults, matching the pre-drop invariant.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e6f8a0b2c4"
down_revision: str | None = "f2a7926009fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("dweller", "is_adult")


def downgrade() -> None:
    op.add_column(
        "dweller",
        sa.Column("is_adult", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
