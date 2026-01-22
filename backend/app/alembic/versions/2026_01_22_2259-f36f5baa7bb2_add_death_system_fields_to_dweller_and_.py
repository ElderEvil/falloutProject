"""add death system fields to dweller and user_profile

Revision ID: f36f5baa7bb2
Revises: 34f9ec11db72
Create Date: 2026-01-22 22:59:33.818004

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f36f5baa7bb2"
down_revision: Union[str, None] = "34f9ec11db72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the DeathCauseEnum type first
    death_cause_enum = sa.Enum("HEALTH", "RADIATION", "INCIDENT", "EXPLORATION", "COMBAT", name="deathcauseenum")
    death_cause_enum.create(op.get_bind(), checkfirst=True)

    # Add death system fields to dweller table
    op.add_column("dweller", sa.Column("is_dead", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("dweller", sa.Column("death_timestamp", sa.DateTime(), nullable=True))
    op.add_column("dweller", sa.Column("death_cause", death_cause_enum, nullable=True))
    op.add_column("dweller", sa.Column("is_permanently_dead", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("dweller", sa.Column("epitaph", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.create_index(op.f("ix_dweller_is_dead"), "dweller", ["is_dead"], unique=False)
    op.create_index(op.f("ix_dweller_is_permanently_dead"), "dweller", ["is_permanently_dead"], unique=False)

    # Add life/death statistics to userprofile table
    op.add_column("userprofile", sa.Column("total_dwellers_born", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("userprofile", sa.Column("total_dwellers_died", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("userprofile", sa.Column("deaths_by_health", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("userprofile", sa.Column("deaths_by_radiation", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("userprofile", sa.Column("deaths_by_incident", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("userprofile", sa.Column("deaths_by_exploration", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("userprofile", sa.Column("deaths_by_combat", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    # Remove life/death statistics from userprofile
    op.drop_column("userprofile", "deaths_by_combat")
    op.drop_column("userprofile", "deaths_by_exploration")
    op.drop_column("userprofile", "deaths_by_incident")
    op.drop_column("userprofile", "deaths_by_radiation")
    op.drop_column("userprofile", "deaths_by_health")
    op.drop_column("userprofile", "total_dwellers_died")
    op.drop_column("userprofile", "total_dwellers_born")

    # Remove death system fields from dweller
    op.drop_index(op.f("ix_dweller_is_permanently_dead"), table_name="dweller")
    op.drop_index(op.f("ix_dweller_is_dead"), table_name="dweller")
    op.drop_column("dweller", "epitaph")
    op.drop_column("dweller", "is_permanently_dead")
    op.drop_column("dweller", "death_cause")
    op.drop_column("dweller", "death_timestamp")
    op.drop_column("dweller", "is_dead")

    # Drop the DeathCauseEnum type
    death_cause_enum = sa.Enum("HEALTH", "RADIATION", "INCIDENT", "EXPLORATION", "COMBAT", name="deathcauseenum")
    death_cause_enum.drop(op.get_bind(), checkfirst=True)
