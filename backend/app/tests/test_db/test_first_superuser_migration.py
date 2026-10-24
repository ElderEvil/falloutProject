import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings


@pytest.mark.parametrize("configured_admin_present", [False, True])
def test_bootstrap_marker_backfill_and_unique_identity(monkeypatch, configured_admin_present):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_24_0002-b4d8f2a6c0e1_pin_first_superuser.py"
    spec = importlib.util.spec_from_file_location("pin_first_superuser", path)
    assert spec
    assert spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("""CREATE TABLE "user" (
            id TEXT PRIMARY KEY, email TEXT, is_superuser BOOLEAN, created_at TEXT
        )""")
        )
        rows = [
            {"id": "old-admin", "email": "renamed@example.com", "is_superuser": True, "created_at": "2020-01-01"},
            {"id": "regular", "email": "player@example.com", "is_superuser": False, "created_at": "2019-01-01"},
        ]
        rows.append({"id": "undated-admin", "email": "undated@example.com", "is_superuser": True, "created_at": None})
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
            text("""INSERT INTO "user" (id, email, is_superuser, created_at)
            VALUES (:id, :email, :is_superuser, :created_at)"""),
            rows,
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
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
        migration.downgrade()
        assert "is_first_superuser" not in [row[1] for row in connection.execute(text('PRAGMA table_info("user")'))]
    engine.dispose()
