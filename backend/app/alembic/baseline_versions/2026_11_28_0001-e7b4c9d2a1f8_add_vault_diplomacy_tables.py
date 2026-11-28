"""add vaultrelation and diplomaticfiling tables

Revision ID: e7b4c9d2a1f8
Revises: b9d4e2f7a1c6
Create Date: 2026-11-28 00:01:00.000000

Persistence for the Envoy Terminal (docs/plans/2026-11-28-vault-diplomacy.md, Slice 1):
one standing per vault pair and one filing per pair per direction.

* ``vaultrelation`` keys the unordered pair: ``vault_a_id`` is always the lower UUID, so
  the unique constraint makes a swapped duplicate impossible.
* ``diplomaticfiling`` carries the structured terms (JSONB), an expiry and an answer.

Status and kind are plain VARCHAR on purpose: the StrEnums need no PostgreSQL enum type,
so there is no ``ALTER TYPE`` here and no enum-label snapshot change. Every timestamp is
``timestamptz`` (the app's UTCDateTime); a naive ``TIMESTAMP`` fails ``alembic check``.
No backfill: both tables are new and empty.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b4c9d2a1f8"
down_revision: str | Sequence[str] | None = "b9d4e2f7a1c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vaultrelation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vault_a_id", sa.Uuid(), nullable=False),
        sa.Column("vault_b_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("standing", sa.Integer(), nullable=False),
        sa.Column("met_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["vault_a_id"], ["vault.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vault_b_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vault_a_id", "vault_b_id", name="uq_vault_relation_pair"),
    )
    op.create_index(op.f("ix_vaultrelation_id"), "vaultrelation", ["id"], unique=False)
    op.create_index(op.f("ix_vaultrelation_vault_a_id"), "vaultrelation", ["vault_a_id"], unique=False)
    op.create_index(op.f("ix_vaultrelation_vault_b_id"), "vaultrelation", ["vault_b_id"], unique=False)
    op.create_index(
        "ix_vaultrelation_status_locked_until", "vaultrelation", ["status", "locked_until"], unique=False
    )

    op.create_table(
        "diplomaticfiling",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("from_vault_id", sa.Uuid(), nullable=False),
        sa.Column("to_vault_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["from_vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diplomaticfiling_id"), "diplomaticfiling", ["id"], unique=False)
    op.create_index(
        op.f("ix_diplomaticfiling_from_vault_id"), "diplomaticfiling", ["from_vault_id"], unique=False
    )
    op.create_index(op.f("ix_diplomaticfiling_to_vault_id"), "diplomaticfiling", ["to_vault_id"], unique=False)
    op.create_index(
        "ix_diplomaticfiling_pair_kind_status",
        "diplomaticfiling",
        ["from_vault_id", "to_vault_id", "kind", "status"],
        unique=False,
    )
    op.create_index(
        "ix_diplomaticfiling_status_expires_at", "diplomaticfiling", ["status", "expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_diplomaticfiling_status_expires_at", table_name="diplomaticfiling")
    op.drop_index("ix_diplomaticfiling_pair_kind_status", table_name="diplomaticfiling")
    op.drop_index(op.f("ix_diplomaticfiling_to_vault_id"), table_name="diplomaticfiling")
    op.drop_index(op.f("ix_diplomaticfiling_from_vault_id"), table_name="diplomaticfiling")
    op.drop_index(op.f("ix_diplomaticfiling_id"), table_name="diplomaticfiling")
    op.drop_table("diplomaticfiling")

    op.drop_index("ix_vaultrelation_status_locked_until", table_name="vaultrelation")
    op.drop_index(op.f("ix_vaultrelation_vault_b_id"), table_name="vaultrelation")
    op.drop_index(op.f("ix_vaultrelation_vault_a_id"), table_name="vaultrelation")
    op.drop_index(op.f("ix_vaultrelation_id"), table_name="vaultrelation")
    op.drop_table("vaultrelation")
