"""Release legacy quest parties that never departed.

Revision ID: d9e2f4a6b801
Revises: b6d8f0a2c913
"""

from alembic import op

revision = "d9e2f4a6b801"
down_revision = "b6d8f0a2c913"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL stores DwellerStatusEnum member names, not their lowercase values.
    op.execute("""
        UPDATE dweller AS d
        SET status = 'IDLE', room_id = NULL
        WHERE d.status = 'QUESTING'
          AND NOT EXISTS (
              SELECT 1
              FROM team_member AS tm
              JOIN team AS t ON t.id = tm.team_id
              JOIN vaultquestcompletionlink AS vq
                ON vq.quest_id = t.quest_id AND vq.vault_id = t.vault_id
              WHERE tm.dweller_id = d.id
                AND vq.started_at IS NOT NULL
                AND NOT vq.is_reward_ready
                AND NOT vq.is_completed
          )
    """)


def downgrade() -> None:
    # Data repair is intentionally irreversible: old postings and intended
    # departures cannot be reconstructed, and putting dwellers back would strand them.
    pass
