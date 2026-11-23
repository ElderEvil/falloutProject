from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db

SCHEMA = (
    "CREATE TABLE objective (id TEXT PRIMARY KEY, category TEXT, challenge TEXT, template_key TEXT, sequence INTEGER)",
    "CREATE TABLE gamestate (id INTEGER PRIMARY KEY)",
    (
        "CREATE TABLE vaultobjectiveprogresslink (vault_id TEXT, objective_id TEXT, progress INTEGER, total INTEGER, "
        "is_completed BOOLEAN, reward_snapshot TEXT)"
    ),
    "INSERT INTO objective VALUES ('water','achievement',' Collect 500 Water ',NULL,NULL)",
    "INSERT INTO objective VALUES ('custom','achievement','Collect 500 Water','custom:water',NULL)",
    "INSERT INTO objective VALUES ('water-first','achievement','Collect 100 Water',NULL,NULL)",
    "INSERT INTO gamestate VALUES (1)",
    "INSERT INTO vaultobjectiveprogresslink VALUES ('vault','water',500,500,0,'17 caps')",
    "INSERT INTO vaultobjectiveprogresslink VALUES ('legacy','water-first',90,100,0,NULL)",
    "INSERT INTO vaultobjectiveprogresslink VALUES ('legacy','water',300,500,0,NULL)",
)


def test_migration_preserves_existing_rewards_and_adopts_tracks():
    migration = load_migration("2026_10_18_0002-b37d2a5f810c_achievement_tracks.py", "objective_tracks_migration")
    with sqlite_db(*SCHEMA) as db:
        bind_op(migration, db)
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
        ).one() == (500, "17 caps")
