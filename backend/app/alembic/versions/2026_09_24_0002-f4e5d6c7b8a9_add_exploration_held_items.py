"""add exploration held items

Revision ID: f4e5d6c7b8a9
Revises: 2e4f6a8b0c1d
Create Date: 2026-09-24 00:02:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4e5d6c7b8a9"
down_revision: str | None = "2e4f6a8b0c1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Items held by an in-progress exploration: exploration_id set, storage_id
    # and dweller_id both NULL. FK-only — no relationship is added.
    op.add_column("weapon", sa.Column("exploration_id", sa.Uuid(), nullable=True))
    op.add_column("outfit", sa.Column("exploration_id", sa.Uuid(), nullable=True))
    op.create_index("ix_weapon_exploration_id", "weapon", ["exploration_id"])
    op.create_index("ix_outfit_exploration_id", "outfit", ["exploration_id"])
    op.create_foreign_key(
        "fk_weapon_exploration_id_exploration",
        "weapon",
        "exploration",
        ["exploration_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_outfit_exploration_id_exploration",
        "outfit",
        "exploration",
        ["exploration_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_outfit_exploration_id_exploration", "outfit", type_="foreignkey")
    op.drop_constraint("fk_weapon_exploration_id_exploration", "weapon", type_="foreignkey")
    op.drop_index("ix_outfit_exploration_id", table_name="outfit")
    op.drop_index("ix_weapon_exploration_id", table_name="weapon")
    op.drop_column("outfit", "exploration_id")
    op.drop_column("weapon", "exploration_id")
