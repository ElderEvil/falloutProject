"""Normalize generated dweller state-of-being values.

Revision ID: c2d4e6f8a0b1
Revises: f7a8b9c0d1e2
Create Date: 2026-08-31 00:00:03.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c2d4e6f8a0b1"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATE_RENAMES = {
    "partially_feral": "wild",
    "fully_feral": "feral",
    "mild_mutation": "mild",
    "severe_mutation": "average",
}


def upgrade() -> None:
    """Update JSONB values that no longer match the dweller response schema."""
    for old_value, new_value in _STATE_RENAMES.items():
        op.execute(
            "UPDATE dweller "
            "SET visual_attributes = jsonb_set(visual_attributes, '{state_of_being}', to_jsonb(CAST("
            f"'{new_value}' AS text))) "
            f"WHERE visual_attributes ->> 'state_of_being' = '{old_value}'"
        )


def downgrade() -> None:
    """Restore the legacy generated values for a database downgrade."""
    for old_value, new_value in _STATE_RENAMES.items():
        op.execute(
            "UPDATE dweller "
            "SET visual_attributes = jsonb_set(visual_attributes, '{state_of_being}', to_jsonb(CAST("
            f"'{old_value}' AS text))) "
            f"WHERE visual_attributes ->> 'state_of_being' = '{new_value}'"
        )
