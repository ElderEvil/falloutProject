"""make hashed_password nullable for provider-only accounts

Revision ID: b0a1c2d3e4f5
Revises: ecbe0fb70132
Create Date: 2026-10-23 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "b0a1c2d3e4f5"
down_revision: str | Sequence[str] | None = "ecbe0fb70132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "user",
        "hashed_password",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        nullable=True,
    )


def downgrade() -> None:
    # Fails while provider-only accounts without a password exist; that is intentional:
    # there is no safe password to invent for them.
    op.alter_column(
        "user",
        "hashed_password",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        nullable=False,
    )
