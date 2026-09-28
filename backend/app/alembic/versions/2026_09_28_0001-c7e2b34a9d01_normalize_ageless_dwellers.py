"""Normalize existing non-human elders and radiation after race immunity changes.

Revision ID: c7e2b34a9d01
Revises: b5a4c3d2e1f0
Create Date: 2026-09-28 00:01:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c7e2b34a9d01"
down_revision: str | None = "b5a4c3d2e1f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preserve real birth dates while removing obsolete visual age and radiation."""
    op.execute(
        "INSERT INTO storage (id, vault_id, used_space, max_space, stimpack, radaway) "
        "SELECT gen_random_uuid(), d.vault_id, 0, 0, 0, 0 FROM dweller d "
        "WHERE d.radaway > 0 AND d.visual_attributes ->> 'race' IN ('ghoul', 'super_mutant', 'synth') "
        "AND NOT EXISTS (SELECT 1 FROM storage s WHERE s.vault_id = d.vault_id) GROUP BY d.vault_id"
    )
    op.execute(
        "UPDATE storage s SET radaway = s.radaway + moved.total FROM "
        "(SELECT vault_id, SUM(radaway) AS total FROM dweller WHERE radaway > 0 "
        "AND visual_attributes ->> 'race' IN ('ghoul', 'super_mutant', 'synth') GROUP BY vault_id) moved "
        "WHERE s.vault_id = moved.vault_id"
    )
    op.execute(
        "UPDATE dweller SET radaway = 0 WHERE radaway > 0 "
        "AND visual_attributes ->> 'race' IN ('ghoul', 'super_mutant', 'synth')"
    )
    # A fresh transactional upgrade added ELDER earlier; compare as text until that value is committed.
    op.execute(
        "UPDATE dweller SET age_group = 'ADULT' WHERE age_group::text = 'ELDER' "
        "AND visual_attributes ->> 'race' IN ('ghoul', 'super_mutant', 'synth')"
    )
    op.execute(
        "UPDATE dweller SET radiation = 0 WHERE radiation > 0 "
        "AND visual_attributes ->> 'race' IN ('ghoul', 'super_mutant', 'synth')"
    )


def downgrade() -> None:
    """No-op: prior age labels and radiation cannot be reconstructed safely."""
