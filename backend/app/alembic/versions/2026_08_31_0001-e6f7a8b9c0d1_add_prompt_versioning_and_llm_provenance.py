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
    """Version prompts and snapshot LLM call provenance."""
    inspector = sa.inspect(op.get_bind())

    prompt_cols = _column_names(inspector, "prompt")
    needs_normalization = "version" not in prompt_cols or "is_active" not in prompt_cols
    if not needs_normalization:
        needs_normalization = bool(
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT EXISTS (SELECT 1 FROM prompt WHERE version IS NULL OR version < 1) "
                    "OR EXISTS (SELECT 1 FROM prompt GROUP BY prompt_name, version HAVING COUNT(*) > 1) "
                    "OR EXISTS (SELECT 1 FROM prompt GROUP BY prompt_name "
                    "HAVING SUM(CASE WHEN is_active THEN 1 ELSE 0 END) != 1)"
                )
            )
            .scalar()
        )
    prompt_indexes = {i["name"] for i in inspector.get_indexes("prompt")}
    prompt_constraints = {c["name"] for c in inspector.get_unique_constraints("prompt")}
    with op.batch_alter_table("prompt") as batch_op:
        if "version" not in prompt_cols:
            batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "is_active" not in prompt_cols:
            batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    if needs_normalization:
        rows = op.get_bind().execute(sa.text("SELECT id, prompt_name FROM prompt ORDER BY prompt_name, id")).mappings()
        versions: dict[str, int] = {}
        normalized = []
        for row in rows:
            version = versions.get(row["prompt_name"], 0) + 1
            versions[row["prompt_name"]] = version
            normalized.append({"id": row["id"], "version": version, "is_active": version == 1})
        if normalized:
            op.get_bind().execute(
                sa.text("UPDATE prompt SET version = :version, is_active = :is_active WHERE id = :id"), normalized
            )

    with op.batch_alter_table("prompt") as batch_op:
        if "version" not in prompt_cols:
            batch_op.alter_column("version", server_default=None)
        if "is_active" not in prompt_cols:
            batch_op.alter_column("is_active", server_default=None)
        for name, column in (
            ("ix_prompt_prompt_name", "prompt_name"),
            ("ix_prompt_entity_id", "entity_id"),
            ("ix_prompt_is_active", "is_active"),
        ):
            if name not in prompt_indexes:
                batch_op.create_index(name, [column], unique=False)
        if "uq_prompt_name_version" not in prompt_constraints:
            batch_op.create_unique_constraint("uq_prompt_name_version", ["prompt_name", "version"])
        if "ix_prompt_active_name" not in prompt_indexes:
            batch_op.create_index(
                "ix_prompt_active_name",
                ["prompt_name"],
                unique=True,
                postgresql_where=sa.text("is_active = true"),
                sqlite_where=sa.text("is_active = true"),
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
    with op.batch_alter_table("prompt") as batch_op:
        batch_op.drop_index("ix_prompt_active_name")
        batch_op.drop_index("ix_prompt_is_active")
        batch_op.drop_constraint("uq_prompt_name_version", type_="unique")
        batch_op.drop_column("is_active")
        batch_op.drop_column("version")
