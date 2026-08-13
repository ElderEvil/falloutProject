"""Backfill quest chain visibility.

Revision ID: 3f13e2c5a7d9
Revises: 2d31a1e4b5c6
Create Date: 2026-08-13 22:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f13e2c5a7d9"
down_revision: str | None = "2d31a1e4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill chain predecessors used to calculate quest-chain visibility."""
    op.execute(
        """
        WITH prerequisites AS (
            SELECT DISTINCT ON (requirement.quest_id)
                requirement.quest_id,
                previous_quest.id AS previous_quest_id
            FROM questrequirement AS requirement
            CROSS JOIN LATERAL (
                SELECT (requirement.requirement_data ->> 'quest_id')::uuid AS id
                WHERE requirement.requirement_data ->> 'quest_id'
                    ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            ) AS prerequisite
            JOIN quest AS previous_quest ON previous_quest.id = prerequisite.id
            WHERE requirement.requirement_type = 'QUEST_COMPLETED'
              AND requirement.is_mandatory
            ORDER BY requirement.quest_id, requirement.id
        )
        UPDATE quest
        SET previous_quest_id = prerequisites.previous_quest_id
        FROM prerequisites
        WHERE quest.id = prerequisites.quest_id
          AND quest.previous_quest_id IS NULL
        """
    )


def downgrade() -> None:
    """The chain-link data backfill intentionally remains after downgrade."""
