import sqlalchemy as sa

from app.tests.test_alembic._support import load_migration, sqlite_db

BACKFILL = load_migration(
    "2026_10_04_0002-8a7c07e1b448_drop_dweller_is_adult.py", "drop_dweller_is_adult"
).BACKFILL_IS_ADULT
INSERTS = tuple(
    f"INSERT INTO dweller (age_group, is_adult) VALUES ('{group}', TRUE)"  # ruff: ignore[hardcoded-sql-expression]
    for group in ("CHILD", "TEEN", "ADULT", "ELDER")
)


def test_downgrade_backfill_preserves_youth():
    with sqlite_db("CREATE TABLE dweller (id INTEGER PRIMARY KEY, age_group TEXT, is_adult BOOLEAN)", *INSERTS) as db:
        db.execute(BACKFILL)
        flags = dict(db.execute(sa.text("SELECT age_group, is_adult FROM dweller")).all())
    assert flags == {"CHILD": False, "TEEN": False, "ADULT": True, "ELDER": True}
