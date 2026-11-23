import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.tests.test_alembic._support import bind_op, column_names, load_migration, sqlite_db

MIGRATION = load_migration("2026_10_24_0002-b4d8f2a6c0e1_pin_first_superuser.py", "pin_first_superuser")


@pytest.mark.parametrize("configured_admin_present", [False, True])
def test_bootstrap_marker_backfill_and_unique_identity(configured_admin_present):
    with sqlite_db(
        'CREATE TABLE "user" (id TEXT PRIMARY KEY, email TEXT, is_superuser BOOLEAN, created_at TEXT)'
    ) as connection:
        rows = [
            {"id": "old-admin", "email": "renamed@example.com", "is_superuser": True, "created_at": "2020-01-01"},
            {"id": "regular", "email": "player@example.com", "is_superuser": False, "created_at": "2019-01-01"},
            {"id": "undated-admin", "email": "undated@example.com", "is_superuser": True, "created_at": None},
        ]
        if configured_admin_present:
            rows.append(
                {
                    "id": "configured",
                    "email": str(settings.FIRST_SUPERUSER_EMAIL),
                    "is_superuser": True,
                    "created_at": "2021-01-01",
                }
            )
        connection.execute(
            text(
                'INSERT INTO "user" (id, email, is_superuser, created_at) '
                "VALUES (:id, :email, :is_superuser, :created_at)"
            ),
            rows,
        )
        bind_op(MIGRATION, connection)
        MIGRATION.upgrade()
        first_id = connection.execute(text('SELECT id FROM "user" WHERE is_first_superuser = true')).scalar_one()
        assert first_id == ("configured" if configured_admin_present else "old-admin")
        connection.execute(
            text('UPDATE "user" SET email = :email WHERE id = :id'), {"id": first_id, "email": "changed@example.com"}
        )
        assert (
            connection.execute(text('SELECT id FROM "user" WHERE is_first_superuser = true')).scalar_one() == first_id
        )
        with pytest.raises(IntegrityError):
            connection.execute(text('UPDATE "user" SET is_first_superuser = true WHERE id = :id'), {"id": "regular"})
        MIGRATION.downgrade()
        assert "is_first_superuser" not in column_names(connection, '"user"')
