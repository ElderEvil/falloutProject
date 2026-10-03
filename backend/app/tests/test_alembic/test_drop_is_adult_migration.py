"""Regression guard for the is_adult drop migration's downgrade backfill.

On rollback, a bare ``server_default=true`` would mark every CHILD/TEEN row as an
adult, and the pre-drop code reads ``~is_adult`` to find apprenticeship candidates.
This pins that the restored flag is reconstructed from ``age_group`` using the same
expression the migration executes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa

MIGRATION_PATH = (
    Path(__file__).parents[2] / "alembic" / "versions" / "2026_10_04_0001-d4e6f8a0b2c4_drop_dweller_is_adult.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("drop_dweller_is_adult", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downgrade_backfill_marks_only_adults_and_elders() -> None:
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE dweller (id INTEGER PRIMARY KEY, age_group TEXT)"))
        for row_id, age_group in enumerate(["CHILD", "TEEN", "ADULT", "ELDER"], start=1):
            conn.execute(
                sa.text("INSERT INTO dweller (id, age_group) VALUES (:id, :age_group)"),
                {"id": row_id, "age_group": age_group},
            )
        conn.execute(sa.text("ALTER TABLE dweller ADD COLUMN is_adult BOOLEAN"))
        conn.execute(migration.BACKFILL_IS_ADULT)
        rows = conn.execute(sa.text("SELECT age_group, is_adult FROM dweller ORDER BY id")).fetchall()

    assert [(age_group, bool(is_adult)) for age_group, is_adult in rows] == [
        ("CHILD", False),
        ("TEEN", False),
        ("ADULT", True),
        ("ELDER", True),
    ]
