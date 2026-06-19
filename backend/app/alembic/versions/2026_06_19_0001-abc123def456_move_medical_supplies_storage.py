"""move stimpack/radaway from vault to storage

Revision ID: abc123def456
Revises: 2512d7563670
Create Date: 2026-06-19 00:01:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "abc123def456"
down_revision: Union[str, None] = "2512d7563670"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to storage table
    op.add_column("storage", sa.Column("stimpack", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("storage", sa.Column("radaway", sa.Integer(), nullable=False, server_default="0"))

    # Enforce bounds at DB level (defense-in-depth beyond Pydantic/SQLModel)
    op.create_check_constraint("ck_storage_stimpack_bounds", "storage", sa.text("stimpack >= 0 AND stimpack <= 10000"))
    op.create_check_constraint("ck_storage_radaway_bounds", "storage", sa.text("radaway >= 0 AND radaway <= 10000"))

    # Copy existing data from vault to storage
    op.execute(
        """
        UPDATE storage
        SET stimpack = vault.stimpack,
            radaway = vault.radaway
        FROM vault
        WHERE storage.vault_id = vault.id
        """
    )

    # Drop old columns from vault table
    op.drop_column("vault", "stimpack_max")
    op.drop_column("vault", "radaway")
    op.drop_column("vault", "stimpack")
    op.drop_column("vault", "radaway_max")


def downgrade() -> None:
    # Drop CHECK constraints before dropping columns
    op.drop_constraint("ck_storage_stimpack_bounds", "storage", type_="check")
    op.drop_constraint("ck_storage_radaway_bounds", "storage", type_="check")

    # Re-add old columns to vault table
    op.add_column("vault", sa.Column("stimpack", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vault", sa.Column("stimpack_max", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vault", sa.Column("radaway", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("vault", sa.Column("radaway_max", sa.Integer(), nullable=False, server_default="0"))

    # Copy data back from storage to vault
    # Note: stimpack_max and radaway_max are intentionally set to 0 because
    # these values are now dynamically computed from rooms (via
    # compute_medical_capacity), making this data-loss acceptable during rollbacks.
    op.execute(
        """
        UPDATE vault
        SET stimpack = storage.stimpack,
            stimpack_max = 0,
            radaway = storage.radaway,
            radaway_max = 0
        FROM storage
        WHERE vault.id = storage.vault_id
        """
    )

    # Drop new columns from storage table
    op.drop_column("storage", "radaway")
    op.drop_column("storage", "stimpack")
