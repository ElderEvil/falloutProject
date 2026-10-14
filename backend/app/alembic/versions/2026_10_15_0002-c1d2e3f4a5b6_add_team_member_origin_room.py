"""add origin room to team member (dispatch provenance)

Revision ID: c1d2e3f4a5b6
Revises: a7d4e1f2c3b4
Create Date: 2026-10-15 00:02:00.000000

Issue 997: an auto-dispatched hazard responder must return to the Response
Station when that was their posting before the incident, while responders posted
elsewhere keep the existing production auto-assign. The pre-dispatch posting is
recorded on the incident roster member (``team_member.origin_room_id``) when the
team is dispatched. Nullable with no backfill: NULL is the correct "no posting to
restore" state for every existing row and for manual responders, so the return
pass keeps today's behaviour for them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "a7d4e1f2c3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("team_member", sa.Column("origin_room_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_team_member_origin_room_id",
        "team_member",
        "room",
        ["origin_room_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_team_member_origin_room_id", "team_member", type_="foreignkey")
    op.drop_column("team_member", "origin_room_id")
