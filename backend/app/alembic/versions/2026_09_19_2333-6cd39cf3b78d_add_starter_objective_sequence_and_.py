"""add starter objective sequence and description

Revision ID: 6cd39cf3b78d
Revises: c9d8e7f6a5b4
Create Date: 2026-09-19 23:33:14.175262

The ``starter`` objective arc needs an explicit ordering (``sequence``) and
player-facing guidance (``description``). Both are nullable: only ``starter``
objectives carry them; every other category leaves them NULL. ``category`` is a
plain VARCHAR(50), so adding the ``starter`` category needs no enum migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlmodel.sql.sqltypes import AutoString

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6cd39cf3b78d"
down_revision: str | None = "c9d8e7f6a5b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("objective", sa.Column("sequence", sa.Integer(), nullable=True))
    op.add_column("objective", sa.Column("description", AutoString(), nullable=True))
    op.create_index(op.f("ix_objective_sequence"), "objective", ["sequence"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_objective_sequence"), table_name="objective")
    op.drop_column("objective", "description")
    op.drop_column("objective", "sequence")
