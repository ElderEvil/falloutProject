"""add contamination team roster and incident participation

Revision ID: 3f8a1c7d9e20
Revises: f2b3c4d5e6a7
Create Date: 2026-09-18 00:00:00.000000
"""

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision = "3f8a1c7d9e20"
down_revision = "f2b3c4d5e6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "incident_participant",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("dweller_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incident.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_id", "dweller_id", name="uq_incident_participant"),
    )
    op.create_index(op.f("ix_incident_participant_id"), "incident_participant", ["id"], unique=False)
    op.create_index(op.f("ix_incident_participant_incident_id"), "incident_participant", ["incident_id"], unique=False)
    op.create_index(op.f("ix_incident_participant_dweller_id"), "incident_participant", ["dweller_id"], unique=False)

    op.create_table(
        "hazard_team_member",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("dweller_id", sa.Uuid(), nullable=False),
        sa.Column("team", sa.Enum("FIRE", "RADIATION", name="hazardteam"), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vault_id", "team", "dweller_id", name="uq_hazard_team_dweller"),
    )
    op.create_index(op.f("ix_hazard_team_member_id"), "hazard_team_member", ["id"], unique=False)
    op.create_index(op.f("ix_hazard_team_member_vault_id"), "hazard_team_member", ["vault_id"], unique=False)
    op.create_index(op.f("ix_hazard_team_member_dweller_id"), "hazard_team_member", ["dweller_id"], unique=False)
    op.create_index(op.f("ix_hazard_team_member_team"), "hazard_team_member", ["team"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_hazard_team_member_team"), table_name="hazard_team_member")
    op.drop_index(op.f("ix_hazard_team_member_dweller_id"), table_name="hazard_team_member")
    op.drop_index(op.f("ix_hazard_team_member_vault_id"), table_name="hazard_team_member")
    op.drop_index(op.f("ix_hazard_team_member_id"), table_name="hazard_team_member")
    op.drop_table("hazard_team_member")
    # The hazardteam type is owned by this table; dropping the table leaves it behind.
    op.execute("DROP TYPE IF EXISTS hazardteam")

    op.drop_index(op.f("ix_incident_participant_dweller_id"), table_name="incident_participant")
    op.drop_index(op.f("ix_incident_participant_incident_id"), table_name="incident_participant")
    op.drop_index(op.f("ix_incident_participant_id"), table_name="incident_participant")
    op.drop_table("incident_participant")
