"""backfill spatial journey distance from the trail

Spatial runs move through the world snapshot and never touched `total_distance`, so 75 journeys
finished reporting "0 miles" however far they walked. The value is derivable: the farthest point the
trail reached, doubled when the run came home along the same line.

Revision ID: b7e2c9d4a1f6
Revises: e0c4a1b7f3d2
Create Date: 2026-11-25
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2c9d4a1f6"
down_revision: str | Sequence[str] | None = "e0c4a1b7f3d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BACKFILL = """
UPDATE exploration
SET total_distance = GREATEST(
    total_distance,
    ROUND((
        SELECT COALESCE(
            MAX(
                sqrt(
                    power((step ->> 'x')::float - origin_x, 2)
                    + power((step ->> 'y')::float - origin_y, 2)
                )
            ),
            0
        )
        FROM jsonb_array_elements(trail) AS step
        WHERE step ? 'x' AND step ? 'y'
    ) * CASE WHEN return_started_at IS NOT NULL THEN 2 ELSE 1 END)
)
WHERE world_version IS NOT NULL
  AND origin_x IS NOT NULL
  AND origin_y IS NOT NULL
  AND jsonb_array_length(trail) > 0
"""


def upgrade() -> None:
    op.execute(BACKFILL)


def downgrade() -> None:
    # No restore: the values this replaced were the defect (zero for every spatial journey), and a
    # downgrade cannot distinguish a backfilled distance from one the legacy generator wrote.
    pass
