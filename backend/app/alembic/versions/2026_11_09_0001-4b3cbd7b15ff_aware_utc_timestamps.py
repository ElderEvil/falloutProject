"""Convert every application timestamp to timezone-aware UTC.

Revision ID: 4b3cbd7b15ff
Revises: f9e8d7c6b5a4
Create Date: 2026-11-09 00:00:00.000000

Legacy values were written as naive UTC. The explicit AT TIME ZONE 'UTC'
expression keeps their instants stable regardless of the migration session timezone.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "4b3cbd7b15ff"
down_revision: str | None = "f9e8d7c6b5a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TIMESTAMP_COLUMNS: dict[str, list[str]] = {
    "account_merge": ["created_at"],
    "ai_settings": ["created_at", "updated_at"],
    "arena_match_event": ["created_at", "updated_at"],
    "arena_state": ["created_at", "updated_at", "last_fight_at", "fight_started_at"],
    "broadcast": ["updated_at", "created_at"],
    "chatmessage": ["created_at"],
    "craftingorder": ["created_at", "updated_at", "started_at", "estimated_completion_at", "completed_at", "cancelled_at"],
    "dweller": ["deleted_at", "created_at", "updated_at", "birth_date", "exit_requested_at", "despair_since", "death_timestamp", "apprentice_started_at", "departed_at", "departure_eligible_at"],
    "dwellerlocation": ["created_at", "updated_at"],
    "expeditionrun": ["created_at", "updated_at", "finished_at"],
    "exploration": ["created_at", "updated_at", "start_time", "end_time", "return_started_at", "return_completes_at", "position_as_of", "paused_at"],
    "gamestate": ["created_at", "updated_at", "last_tick_time", "last_activity_time", "last_presence_at", "daily_objectives_period", "weekly_objectives_period", "water_empty_since", "paused_at", "resumed_at"],
    "incident": ["created_at", "updated_at", "start_time", "end_time"],
    "incident_event": ["created_at", "updated_at"],
    "incident_participant": ["created_at", "updated_at"],
    "junk": ["created_at", "updated_at"],
    "llminteraction": ["created_at"],
    "notification": ["created_at", "read_at"],
    "oauth_account": ["created_at", "updated_at"],
    "outfit": ["created_at", "updated_at"],
    "pet": ["created_at", "updated_at"],
    "pregnancy": ["created_at", "updated_at", "conceived_at", "due_at"],
    "quest": ["created_at", "updated_at"],
    "relationship": ["created_at", "updated_at"],
    "room": ["created_at", "updated_at", "last_rush_at"],
    "team": ["created_at", "updated_at"],
    "team_member": ["created_at", "updated_at"],
    "training": ["created_at", "updated_at", "started_at", "estimated_completion_at", "completed_at"],
    "user": ["deleted_at", "created_at", "updated_at", "password_reset_expires", "username_changed_at", "email_changed_at"],
    "userprofile": ["created_at", "updated_at"],
    "vault": ["deleted_at", "created_at", "updated_at", "last_exit_request_at", "arena_morale_awarded_at"],
    "vault_recipe_unlock": ["unlocked_at"],
    "vault_theme": ["crafted_at"],
    "vaultlocationstate": ["created_at", "updated_at", "cleared_at", "reclear_available_at"],
    "vaultquestcompletionlink": ["started_at", "return_started_at", "return_completes_at", "completed_at"],
    "vaultslot": ["created_at", "updated_at"],
    "weapon": ["created_at", "updated_at", "last_maintenance_trial_at"],
    "worldlocation": ["created_at", "updated_at"],
    "worldsnapshot": ["created_at", "updated_at"],
}


def _convert(target_type: str) -> None:
    for table, columns in _TIMESTAMP_COLUMNS.items():
        clauses = ", ".join(
            f'ALTER COLUMN "{column}" TYPE {target_type} USING "{column}" AT TIME ZONE \'UTC\''
            for column in columns
        )
        op.execute(f'ALTER TABLE "{table}" {clauses}')


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '15min'")
    _convert("timestamptz")


def downgrade() -> None:
    _convert("timestamp")
