"""add_wasteland_location_coord_constraints

Revision ID: 4408ea93bd5b
Revises: edb924d8dbeb
Create Date: 2026-08-07 10:23:18.369491

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4408ea93bd5b"
down_revision: str | None = "edb924d8dbeb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- CHECK constraints for coord_x / coord_y range ---
    op.create_check_constraint(
        "ck_wasteland_location_coord_x_range",
        "wastelandlocation",
        "coord_x >= 0 AND coord_x <= 100",
    )
    op.create_check_constraint(
        "ck_wasteland_location_coord_y_range",
        "wastelandlocation",
        "coord_y >= 0 AND coord_y <= 100",
    )

    # --- Unique constraint on (vault_id, coord_x, coord_y) ---
    op.create_unique_constraint(
        "uq_wasteland_location_vault_coords",
        "wastelandlocation",
        ["vault_id", "coord_x", "coord_y"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_wasteland_location_vault_coords", "wastelandlocation", type_="unique")
    op.drop_constraint("ck_wasteland_location_coord_y_range", "wastelandlocation", type_="check")
    op.drop_constraint("ck_wasteland_location_coord_x_range", "wastelandlocation", type_="check")
