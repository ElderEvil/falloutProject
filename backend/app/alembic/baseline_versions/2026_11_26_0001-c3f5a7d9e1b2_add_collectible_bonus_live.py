"""record whether a collectible claim still pays its finder

Death and recycling clear the dweller's ``collectible_bonus``/``magazine_boon`` while the vault's
claim stays behind as found history. Readback could only infer liveness from a per-stat sum, which
cannot say which claim was lost once the same vault re-recruits that dweller and they find another
collectible of the same stat. The claim now records the answer at the moment the bonus is cleared.

No backfill: existing rows default to live, and readback also checks the finder's live bonus map,
so a legacy claim whose bonus was already cleared still reads as 0. The flag makes the next clear
exact instead of inferred.

Revision ID: c3f5a7d9e1b2
Revises: b7e2c9d4a1f6
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f5a7d9e1b2"
down_revision: str | Sequence[str] | None = "b7e2c9d4a1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vaultcollectible",
        sa.Column("bonus_live", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("vaultcollectible", "bonus_live")
