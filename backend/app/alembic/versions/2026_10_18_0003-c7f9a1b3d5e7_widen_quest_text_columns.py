"""Widen quest text columns beyond the seeder's prose length.

The quest catalog grew past the original 255/64 limits: ten quest texts are
260-294 characters. PostgreSQL enforced the VARCHAR limits (the seeder crashed
at startup); SQLite does not, so the suite never caught it. The columns are
widened to 500/128 and the QuestBase limits rise to match, letting the seeder
persist the authored texts verbatim.

Prod hotfix note: production columns were already ALTERed in place and the
over-length rows trimmed back to fit the old schema limits. This migration
realigns the schema with that state (lengthening here is a no-op for rows
already within the new bounds) and the seeder restores the full authored text
on its next vault-scoped sync pass.
"""

import sqlalchemy as sa
from alembic import op

revision = "c7f9a1b3d5e7"
down_revision = "b37d2a5f810c"
branch_labels = None
depends_on = None

WIDENED_COLUMNS = [
    ("long_description", 255, 500),
    ("requirements", 255, 500),
    ("rewards", 255, 500),
    ("short_description", 64, 128),
]


def upgrade() -> None:
    for column, old, new in WIDENED_COLUMNS:
        op.alter_column("quest", column, type_=sa.VARCHAR(new), existing_type_=sa.VARCHAR(old), existing_nullable=False)


def downgrade() -> None:
    for column, old, _new in WIDENED_COLUMNS:
        op.alter_column("quest", column, type_=sa.VARCHAR(old), existing_type_=sa.VARCHAR(new), existing_nullable=False)
