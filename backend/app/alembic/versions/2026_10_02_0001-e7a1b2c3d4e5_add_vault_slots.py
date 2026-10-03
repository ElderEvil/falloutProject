"""add vault slots

Revision ID: e7a1b2c3d4e5
Revises: c19031dc6b22
Create Date: 2026-10-02 00:01:00.000000

Persisted vault map placement: each vault claims one unique slot on the shared
atlas, discoverable by every user. Existing vaults are backfilled deterministically
by vault number (0-based); the backfill is guarded by ``NOT EXISTS`` so it is
idempotent. Precondition: ``VAULT_SLOT_COUNT`` must be at least the live vault
count before upgrading — the backfill numbers every live vault without an upper
bound, and indices at or above the configured count wrap onto occupied cells
(``slot_index % count``) while new-vault claims only try ``0..count-1``.
``downgrade()`` drops the table, losing all slot placement. No enum
migration: ``slot_index`` is an int.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e7a1b2c3d4e5"
down_revision: str | None = "c19031dc6b22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL_SQL = sa.text(
    """
    INSERT INTO vaultslot (id, slot_index, vault_id, created_at, updated_at)
    SELECT gen_random_uuid(),
           (row_number() OVER (ORDER BY v.number) - 1)::int,
           v.id, now(), now()
    FROM vault v
    WHERE v.is_deleted = false
      AND NOT EXISTS (SELECT 1 FROM vaultslot s WHERE s.vault_id = v.id)
    """
)


def upgrade() -> None:
    op.create_table(
        "vaultslot",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("vault_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_index", name="uq_vault_slot_index"),
        sa.UniqueConstraint("vault_id", name="uq_vault_slot_vault"),
    )
    op.create_index("ix_vaultslot_id", "vaultslot", ["id"])
    op.execute(BACKFILL_SQL)


def downgrade() -> None:
    op.drop_table("vaultslot")
