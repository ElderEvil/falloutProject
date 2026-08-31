"""Add prompt versioning and LLM interaction provenance.

Revision ID: e6f7a8b9c0d1
Revises: b4c5d6e7f8a9
Create Date: 2026-08-31 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "b4c5d6e7f8a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    """Version the prompt registry and snapshot LLM call provenance.

    server_default backfills existing rows (version=1, is_active=true) and is
    dropped afterwards so the schema matches the model metadata. Guards keep
    the migration safe to re-run after a partially applied attempt.
    """
    inspector = sa.inspect(op.get_bind())

    prompt_cols = _column_names(inspector, "prompt")
    if "version" not in prompt_cols:
        op.add_column("prompt", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    if "is_active" not in prompt_cols:
        op.add_column("prompt", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column("prompt", "version", server_default=None)
    op.alter_column("prompt", "is_active", server_default=None)

    if "uq_prompt_name_version" not in {c["name"] for c in inspector.get_unique_constraints("prompt")}:
        op.create_unique_constraint("uq_prompt_name_version", "prompt", ["prompt_name", "version"])

    prompt_indexes = {i["name"] for i in inspector.get_indexes("prompt")}
    # Pre-existing field indexes were silently skipped (pydantic Field import); backfill them for metadata parity.
    for name, column in (
        ("ix_prompt_prompt_name", "prompt_name"),
        ("ix_prompt_entity_id", "entity_id"),
        ("ix_prompt_is_active", "is_active"),
    ):
        if name not in prompt_indexes:
            op.create_index(name, "prompt", [column], unique=False)
    if "ix_prompt_active_name" not in prompt_indexes:
        op.create_index(
            "ix_prompt_active_name",
            "prompt",
            ["prompt_name"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )

    interaction_cols = _column_names(inspector, "llminteraction")
    provenance_columns = {
        "provider": sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        "model": sa.Column("model", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        "instructions_hash": sa.Column("instructions_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        "instructions_snapshot": sa.Column("instructions_snapshot", sa.Text(), nullable=True),
    }
    for name, column in provenance_columns.items():
        if name not in interaction_cols:
            op.add_column("llminteraction", column)


def downgrade() -> None:
    """Remove prompt versioning and LLM provenance columns."""
    op.drop_column("llminteraction", "instructions_snapshot")
    op.drop_column("llminteraction", "instructions_hash")
    op.drop_column("llminteraction", "model")
    op.drop_column("llminteraction", "provider")
    op.drop_index("ix_prompt_active_name", table_name="prompt")
    op.drop_index("ix_prompt_is_active", table_name="prompt")
    op.drop_constraint("uq_prompt_name_version", "prompt", type_="unique")
    op.drop_column("prompt", "is_active")
    op.drop_column("prompt", "version")
