"""add_cascade_delete_to_notification_vault_id

Revision ID: 3d3a9385bae4
Revises: 3c8d45e9f1a2
Create Date: 2026-02-10 22:34:32.909091

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "3d3a9385bae4"
down_revision: Union[str, None] = "3c8d45e9f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing foreign key without cascade
    op.execute("ALTER TABLE notification DROP CONSTRAINT IF EXISTS notification_vault_id_fkey")

    # Recreate the foreign key with ON DELETE CASCADE
    op.create_foreign_key(
        "notification_vault_id_fkey", "notification", "vault", ["vault_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    # Drop the cascade foreign key
    op.execute("ALTER TABLE notification DROP CONSTRAINT IF EXISTS notification_vault_id_fkey")

    # Recreate the foreign key without cascade
    op.create_foreign_key(
        "notification_vault_id_fkey",
        "notification",
        "vault",
        ["vault_id"],
        ["id"],
    )
