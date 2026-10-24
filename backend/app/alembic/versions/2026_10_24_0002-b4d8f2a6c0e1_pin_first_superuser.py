"""Pin the first superuser to a durable account identity.

Revision ID: b4d8f2a6c0e1
Revises: a9f8e7d6c5b4
"""

from alembic import op
import sqlalchemy as sa

revision = "b4d8f2a6c0e1"
down_revision = "a9f8e7d6c5b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.config import settings

    op.add_column("user", sa.Column("is_first_superuser", sa.Boolean(), server_default=sa.false(), nullable=False))
    # Existing accounts must be backfilled in this migration. Prefer the
    # configured bootstrap admin; legacy installations may have renamed it,
    # so fall back to the earliest-created superuser. Later promotions and
    # email changes never transfer this marker.
    op.get_bind().execute(
        sa.text(
            '''UPDATE "user" SET is_first_superuser = true WHERE id = (
                SELECT id FROM "user" WHERE is_superuser = true
                ORDER BY CASE WHEN email = :email THEN 0 ELSE 1 END,
                         created_at ASC NULLS LAST, id ASC
                LIMIT 1
            )'''
        ),
        {"email": str(settings.FIRST_SUPERUSER_EMAIL)},
    )
    op.create_index(
        "uq_user_first_superuser", "user", ["is_first_superuser"], unique=True,
        postgresql_where=sa.text("is_first_superuser"), sqlite_where=sa.text("is_first_superuser"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_first_superuser", table_name="user")
    op.drop_column("user", "is_first_superuser")
