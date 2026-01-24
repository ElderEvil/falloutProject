"""remove_unique_constraint_from_item_names

Revision ID: 74d6a11adead
Revises: f36f5baa7bb2
Create Date: 2026-01-24 14:53:06.689557

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "74d6a11adead"
down_revision: Union[str, None] = "f36f5baa7bb2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove unique constraints from item name columns
    op.drop_index("ix_junk_name", table_name="junk")
    op.create_index(op.f("ix_junk_name"), "junk", ["name"], unique=False)

    op.drop_index("ix_weapon_name", table_name="weapon")
    op.create_index(op.f("ix_weapon_name"), "weapon", ["name"], unique=False)

    op.drop_index("ix_outfit_name", table_name="outfit")
    op.create_index(op.f("ix_outfit_name"), "outfit", ["name"], unique=False)


def downgrade() -> None:
    # Restore unique constraints (will fail if duplicates exist)
    op.drop_index(op.f("ix_outfit_name"), table_name="outfit")
    op.create_index("ix_outfit_name", "outfit", ["name"], unique=True)

    op.drop_index(op.f("ix_weapon_name"), table_name="weapon")
    op.create_index("ix_weapon_name", "weapon", ["name"], unique=True)

    op.drop_index(op.f("ix_junk_name"), table_name="junk")
    op.create_index("ix_junk_name", "junk", ["name"], unique=True)
