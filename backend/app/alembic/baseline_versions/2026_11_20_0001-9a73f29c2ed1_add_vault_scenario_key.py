"""Record vault scenario opt-in for ongoing rules."""

import sqlalchemy as sa
from alembic import op

revision = "9a73f29c2ed1"
down_revision = "squash_4b3cbd7b15ff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older vaults did not record opt-in. Their number alone is not evidence.
    op.add_column("vault", sa.Column("scenario_key", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("vault", "scenario_key")
