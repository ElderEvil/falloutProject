"""repair the Collect 3 Outfits reward to a catalog outfit

Revision ID: cad3b442a260
Revises: c4d5e6f7a8b9
Create Date: 2026-09-30 00:02:00.000000

Seeding is insert-only, so editing an existing objective's reward in
``daily.json`` never reaches an already-seeded row. Move the "Collect 3 Outfits"
reward off the non-catalog ``outfit:Vault Suit`` (which produced a phantom
outfit) onto a real catalog item.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cad3b442a260"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHALLENGE = "Collect 3 Outfits"
_OLD_REWARD = "outfit:Vault Suit"
_NEW_REWARD = "outfit:Mechanic jumpsuit"


def upgrade() -> None:
    op.execute(
        f"UPDATE objective SET reward = '{_NEW_REWARD}' "
        f"WHERE challenge = '{_CHALLENGE}' AND reward = '{_OLD_REWARD}'"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE objective SET reward = '{_OLD_REWARD}' "
        f"WHERE challenge = '{_CHALLENGE}' AND reward = '{_NEW_REWARD}'"
    )
