"""freeze Combat Zone terminal stances and protect match history

Revision ID: b9d4e2f7a1c6
Revises: d1e4b8c2a9f5
Create Date: 2026-11-27 00:02:00.000000

Adds the terminal stances to finished matches so history does not read the reused party
row. Individual dweller hard deletion is refused in the service layer while a party
references the row; the foreign key stays CASCADE so normal whole-vault deletion still
cascades. Historical matches keep NULL stances; the service falls back to the party
stance for those rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b9d4e2f7a1c6"
down_revision: str | Sequence[str] | None = "d1e4b8c2a9f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("combat_zone_match", sa.Column("party_a_stance", sa.String(length=16), nullable=True))
    op.add_column("combat_zone_match", sa.Column("party_b_stance", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("combat_zone_match", "party_b_stance")
    op.drop_column("combat_zone_match", "party_a_stance")
