"""add item_data to quest_reward

Revision ID: a209e58a23bd
Revises: 579eec54af0c
Create Date: 2026-02-13 15:27:57.207059

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a209e58a23bd"
down_revision: Union[str, None] = "579eec54af0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("questreward", sa.Column("item_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("questreward", "item_data")
