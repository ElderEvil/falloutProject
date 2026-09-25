"""add expeditionrun open vault+site unique index

Revision ID: f2cfb4f037d0
Revises: b74a718e1e92
Create Date: 2026-09-25 18:25:45.371966

At most one open run per vault+site (D4-B): a partial unique index on
(vault_id, site_id) where status is ENTERED/IN_ROOM. Complements the existing
per-exploration index; the exclusive index also removes the concurrent-finale
race, so no payout-claim lock is needed.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2cfb4f037d0"
down_revision: str | None = "b74a718e1e92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_expeditionrun_open_vault_site",
        "expeditionrun",
        ["vault_id", "site_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ENTERED', 'IN_ROOM')"),
    )


def downgrade() -> None:
    op.drop_index("uq_expeditionrun_open_vault_site", table_name="expeditionrun")
