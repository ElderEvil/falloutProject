"""add monthly_token_limit to user

Revision ID: de6116eac92a
Revises: b19deb098d13
Create Date: 2026-03-13 19:30:48.920222

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "de6116eac92a"
down_revision: Union[str, None] = "b19deb098d13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("monthly_token_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "monthly_token_limit")
