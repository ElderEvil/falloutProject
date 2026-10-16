"""widen location descriptions

Revision ID: f1e2d3c4b5a6
Revises: c3a9f1e2d4b7
Create Date: 2026-10-16

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, None] = "c3a9f1e2d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("worldlocation", "description", type_=sa.String(length=1000), existing_nullable=True)
    op.alter_column("vaultlocationstate", "description", type_=sa.String(length=1000), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("worldlocation", "description", type_=sa.String(length=255), existing_nullable=True)
    op.alter_column("vaultlocationstate", "description", type_=sa.String(length=255), existing_nullable=True)
