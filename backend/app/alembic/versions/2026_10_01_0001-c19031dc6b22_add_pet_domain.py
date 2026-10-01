"""add pet domain

Revision ID: c19031dc6b22
Revises: 907b110e6ae4
Create Date: 2026-10-01 00:01:00.000000

Pets graduate from generic ``Item(item_type='pet')`` rows to a dedicated
``pet`` table (plan §5.5). Legacy pet Items are backfilled into ``pet`` with
``legacy_item_id`` pointing at the original row, then deleted from ``item``.
The backfill is guarded by ``NOT EXISTS`` so it is idempotent; ``downgrade()``
re-inserts the legacy ``item`` rows (pets minted after the migration are lost)
and drops the table. No enum migration: ``rarity`` reuses the existing
``rarityenum``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c19031dc6b22"
down_revision: str | None = "907b110e6ae4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL_SQL = sa.text(
    """
    INSERT INTO pet (id, name, rarity, value, image_url, storage_id, legacy_item_id, created_at, updated_at)
    SELECT id, name, rarity, value, image_url, storage_id, id, now(), now()
    FROM item
    WHERE item_type = 'pet'
      AND NOT EXISTS (SELECT 1 FROM pet p WHERE p.legacy_item_id = item.id)
    """
)
DELETE_LEGACY_SQL = sa.text("DELETE FROM item WHERE item_type = 'pet'")
RESTORE_LEGACY_SQL = sa.text(
    """
    INSERT INTO item (id, name, rarity, value, image_url, item_type, storage_id)
    SELECT legacy_item_id, name, rarity, value, image_url, 'pet', storage_id
    FROM pet
    WHERE legacy_item_id IS NOT NULL
    """
)


def upgrade() -> None:
    rarity_enum = postgresql.ENUM("COMMON", "RARE", "LEGENDARY", name="rarityenum", create_type=False)

    op.create_table(
        "pet",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("rarity", rarity_enum, nullable=False),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("image_url", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dweller_id", sa.Uuid(), nullable=True),
        sa.Column("storage_id", sa.Uuid(), nullable=True),
        sa.Column("legacy_item_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint("dweller_id IS NULL OR storage_id IS NULL", name="ck_pet_dweller_storage_xor"),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"]),
        sa.ForeignKeyConstraint(["storage_id"], ["storage.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pet_id"), "pet", ["id"], unique=False)
    op.create_index(op.f("ix_pet_name"), "pet", ["name"], unique=False)
    op.create_index(op.f("ix_pet_dweller_id"), "pet", ["dweller_id"], unique=False)
    op.create_index(op.f("ix_pet_storage_id"), "pet", ["storage_id"], unique=False)
    op.create_index(op.f("ix_pet_legacy_item_id"), "pet", ["legacy_item_id"], unique=True)

    conn = op.get_bind()
    conn.execute(BACKFILL_SQL)
    conn.execute(DELETE_LEGACY_SQL)


def downgrade() -> None:
    """Re-insert legacy pet Items, then drop the table.

    Pets minted after the migration (``legacy_item_id IS NULL``) are lost.
    """
    conn = op.get_bind()
    conn.execute(RESTORE_LEGACY_SQL)

    op.drop_index(op.f("ix_pet_legacy_item_id"), table_name="pet")
    op.drop_index(op.f("ix_pet_storage_id"), table_name="pet")
    op.drop_index(op.f("ix_pet_dweller_id"), table_name="pet")
    op.drop_index(op.f("ix_pet_name"), table_name="pet")
    op.drop_index(op.f("ix_pet_id"), table_name="pet")
    op.drop_table("pet")