"""Adopt track metadata without rewriting earned progress."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_preserves_existing_rewards_and_adopts_tracks(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_18_0002-b37d2a5f810c_achievement_tracks.py"
    spec = importlib.util.spec_from_file_location("objective_tracks_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as db:
        db.exec_driver_sql(
            "CREATE TABLE objective (id TEXT PRIMARY KEY, category TEXT, challenge TEXT, template_key TEXT, sequence INTEGER)"
        )
        db.exec_driver_sql("CREATE TABLE gamestate (id INTEGER PRIMARY KEY)")
        db.exec_driver_sql(
            "CREATE TABLE vaultobjectiveprogresslink (vault_id TEXT, objective_id TEXT, progress INTEGER, total INTEGER, is_completed BOOLEAN, reward_snapshot TEXT)"
        )
        db.exec_driver_sql("INSERT INTO objective VALUES ('water','achievement',' Collect 500 Water ',NULL,NULL)")
        db.exec_driver_sql(
            "INSERT INTO objective VALUES ('custom','achievement','Collect 500 Water','custom:water',NULL)"
        )
        db.exec_driver_sql("INSERT INTO objective VALUES ('water-first','achievement','Collect 100 Water',NULL,NULL)")
        db.exec_driver_sql("INSERT INTO gamestate VALUES (1)")
        db.exec_driver_sql("INSERT INTO vaultobjectiveprogresslink VALUES ('vault','water',500,500,0,'17 caps')")
        db.exec_driver_sql("INSERT INTO vaultobjectiveprogresslink VALUES ('legacy','water-first',90,100,0,NULL)")
        db.exec_driver_sql("INSERT INTO vaultobjectiveprogresslink VALUES ('legacy','water',300,500,0,NULL)")
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(db)))
        migration.upgrade()
        assert db.exec_driver_sql("SELECT track_key,sequence FROM objective WHERE id='water'").one() == (
            "collect:water",
            2,
        )
        assert (
            db.exec_driver_sql("SELECT template_key FROM objective WHERE id='water'").scalar_one()
            == "achievement:collect 500 water"
        )
        assert db.exec_driver_sql("SELECT track_key FROM objective WHERE id='custom'").scalar_one() is None
        assert db.exec_driver_sql(
            "SELECT progress,total,is_completed,reward_snapshot,is_locked FROM vaultobjectiveprogresslink WHERE vault_id='vault'"
        ).one() == (500, 500, 0, "17 caps", 0)
        assert db.exec_driver_sql(
            "SELECT objective_id,progress,is_locked FROM vaultobjectiveprogresslink WHERE vault_id='legacy' ORDER BY objective_id"
        ).all() == [("water", 300, 1), ("water-first", 90, 0)]
        assert not db.exec_driver_sql("SELECT achievement_tracks_initialized FROM gamestate").scalar_one()
        migration.downgrade()
        assert db.exec_driver_sql(
            "SELECT progress,reward_snapshot FROM vaultobjectiveprogresslink WHERE vault_id='vault'"
        ).one() == (
            500,
            "17 caps",
        )
    engine.dispose()
