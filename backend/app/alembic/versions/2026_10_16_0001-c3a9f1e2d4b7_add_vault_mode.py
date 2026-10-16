"""add_vault_mode

Revision ID: c3a9f1e2d4b7
Revises: a2b4c6d8e0f2
Create Date: 2026-10-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a9f1e2d4b7"
down_revision: Union[str, None] = "a2b4c6d8e0f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 'standard' is the correct value for every pre-existing vault, so the server
    # default doubles as the migration backfill and no data update is required.
    op.add_column(
        "vault",
        sa.Column("vault_mode", sa.String(length=50), nullable=False, server_default="standard"),
    )


def downgrade() -> None:
    op.drop_column("vault", "vault_mode")
