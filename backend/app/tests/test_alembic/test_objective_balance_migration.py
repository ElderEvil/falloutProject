"""Run the objective catalog migration against persisted legacy rows."""

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_preserves_earned_claims_and_catalog_identity(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_13_0003-d4b9f62ce731_balance_objectives.py"
    spec = importlib.util.spec_from_file_location("balance_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = sa.MetaData()
    objective = sa.Table(
        "objective",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("challenge", sa.String()),
        sa.Column("reward", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("objective_type", sa.String()),
        sa.Column("target_entity", sa.JSON()),
        sa.Column("target_amount", sa.Integer()),
        sa.Column("sequence", sa.Integer()),
        sa.Column("description", sa.String()),
    )
    link = sa.Table(
        "vaultobjectiveprogresslink",
        metadata,
        sa.Column("vault_id", sa.Uuid(), primary_key=True),
        sa.Column("objective_id", sa.Uuid(), primary_key=True),
        sa.Column("progress", sa.Integer()),
        sa.Column("total", sa.Integer()),
        sa.Column("is_completed", sa.Boolean()),
    )
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        metadata.create_all(connection)
        identifier = uuid4()
        connection.execute(
            objective.insert().values(
                id=identifier,
                challenge="Collect 150 Power",
                reward="100 power",
                category="daily",
                objective_type="collect",
                target_entity={"resource_type": "power"},
                target_amount=150,
            )
        )
        for progress, completed in [(150, False), (75, False), (150, True)]:
            connection.execute(
                link.insert().values(
                    vault_id=uuid4(), objective_id=identifier, progress=progress, total=150, is_completed=completed
                )
            )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        upgraded = sa.MetaData()
        upgraded.reflect(connection)
        objectives, links = upgraded.tables["objective"], upgraded.tables["vaultobjectiveprogresslink"]
        daily = connection.execute(sa.select(objectives).where(objectives.c.id == identifier)).mappings().one()
        assert daily["challenge"] == "Collect 150 Power"
        assert daily["reward"] == "25 caps"
        assert daily["template_key"] == "daily:collect 150 power"
        assert len(connection.execute(sa.select(objectives)).all()) == 95
        snapshots = connection.execute(sa.select(links)).mappings().all()
        assert {row["reward_snapshot"] for row in snapshots if row["progress"] == 150} == {"100 power"}
        assert next(row for row in snapshots if row["progress"] == 75)["reward_snapshot"] is None
        assert all(row["credited_dweller_ids"] == [] for row in snapshots)
        source = Path(__file__).parents[2] / "data/objectives"
        catalog = {row["template_key"]: row for file in source.glob("*.json") for row in json.loads(file.read_text())}
        frozen = {
            row["template_key"]: {key: value for key, value in row.items() if key != "legacy_challenge"}
            for row in migration._CATALOG
        }
        assert frozen == catalog
        migration.downgrade()
        assert len(connection.execute(sa.select(objectives)).all()) == 95
    engine.dispose()
