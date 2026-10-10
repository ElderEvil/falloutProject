"""The is_adult drop must restore youth flags correctly on rollback."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa

MIGRATION = next(Path(__file__).resolve().parents[2].joinpath("alembic", "versions").glob("*_drop_dweller_is_adult.py"))


def load_backfill():
    spec = importlib.util.spec_from_file_location("drop_dweller_is_adult", MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BACKFILL_IS_ADULT


def test_downgrade_backfill_preserves_youth():
    """A bare server_default would mark every CHILD/TEEN row as an adult."""
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE dweller (id INTEGER PRIMARY KEY, age_group TEXT, is_adult BOOLEAN)"))
        for age_group in ("CHILD", "TEEN", "ADULT", "ELDER"):
            connection.execute(
                sa.text("INSERT INTO dweller (age_group, is_adult) VALUES (:age_group, TRUE)"),
                {"age_group": age_group},
            )
        connection.execute(load_backfill())
        flags = dict(connection.execute(sa.text("SELECT age_group, is_adult FROM dweller")).all())

    assert flags == {"CHILD": False, "TEEN": False, "ADULT": True, "ELDER": True}
