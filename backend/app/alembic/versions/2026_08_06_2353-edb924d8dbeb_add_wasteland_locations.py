"""add_wasteland_locations

Revision ID: edb924d8dbeb
Revises: e4af3f6a7756
Create Date: 2026-08-06 23:53:52.105475

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "edb924d8dbeb"
down_revision: str | None = "e4af3f6a7756"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- wastelandlocation table ---
    # The inline sa.Enum() creates the PG enum type automatically via
    # _on_table_create.  UPPERCASE labels match Python enum member NAMES
    # (SQLModel/SQLAlchemy persist member names, not values).
    # This matches the pattern used by the initial migration for notificationtype,
    # roomtypeenum, explorationstatus, etc.
    op.create_table(
        "wastelandlocation",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("normalized_name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "ORIGIN",
                "VISITED",
                "DISCOVERY",
                "HOME_VAULT",
                name="locationtypeenum",
            ),
            nullable=False,
        ),
        sa.Column("coord_x", sa.Float(), nullable=False),
        sa.Column("coord_y", sa.Float(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vault_id", sa.Uuid(), nullable=False),
        sa.Column("exploration_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vault_id", "normalized_name", name="uq_wasteland_location_vault_name"),
        sa.ForeignKeyConstraint(["vault_id"], ["vault.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exploration_id"], ["exploration.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_wastelandlocation_id"), "wastelandlocation", ["id"], unique=False)
    op.create_index(op.f("ix_wastelandlocation_normalized_name"), "wastelandlocation", ["normalized_name"], unique=False)
    op.create_index(op.f("ix_wastelandlocation_vault_id"), "wastelandlocation", ["vault_id"], unique=False)

    # --- dwellerlocation table ---
    op.create_table(
        "dwellerlocation",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column(
            "relation",
            sa.Enum(
                "ORIGIN",
                "VISITED",
                name="dwellerlocationrelationenum",
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dweller_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dweller_id", "location_id", "relation", name="uq_dweller_location_relation"),
        sa.ForeignKeyConstraint(["dweller_id"], ["dweller.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["wastelandlocation.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_dwellerlocation_dweller_id"), "dwellerlocation", ["dweller_id"], unique=False)
    op.create_index(op.f("ix_dwellerlocation_id"), "dwellerlocation", ["id"], unique=False)
    op.create_index(op.f("ix_dwellerlocation_location_id"), "dwellerlocation", ["location_id"], unique=False)


def downgrade() -> None:
    # Drop tables first (they depend on the enum types)
    op.drop_index(op.f("ix_dwellerlocation_location_id"), table_name="dwellerlocation")
    op.drop_index(op.f("ix_dwellerlocation_id"), table_name="dwellerlocation")
    op.drop_index(op.f("ix_dwellerlocation_dweller_id"), table_name="dwellerlocation")
    op.drop_table("dwellerlocation")

    op.drop_index(op.f("ix_wastelandlocation_vault_id"), table_name="wastelandlocation")
    op.drop_index(op.f("ix_wastelandlocation_normalized_name"), table_name="wastelandlocation")
    op.drop_index(op.f("ix_wastelandlocation_id"), table_name="wastelandlocation")
    op.drop_table("wastelandlocation")

    # Drop enum types
    sa.Enum(name="dwellerlocationrelationenum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="locationtypeenum").drop(op.get_bind(), checkfirst=True)
