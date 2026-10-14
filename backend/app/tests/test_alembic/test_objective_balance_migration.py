"""Objective catalog migrations: rebalanced payouts never rewrite stored claims."""

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

VERSIONS = Path(__file__).parents[2] / "alembic/versions"
OBJECTIVES = Path(__file__).parents[2] / "data/objectives"
BALANCE_MIGRATION = "2026_10_13_0003-d4b9f62ce731_balance_objectives.py"
SPINE_MIGRATION = "2026_10_14_0001-e5c2b7f19a04_spine_starter_objectives.py"


def _load(filename):
    spec = importlib.util.spec_from_file_location(filename, VERSIONS / filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _json_catalog():
    return {row["template_key"]: row for file in OBJECTIVES.glob("*.json") for row in json.loads(file.read_text())}


def _frozen_catalog(migration):
    return {
        row["template_key"]: {key: value for key, value in row.items() if key != "legacy_challenge"}
        for row in migration._CATALOG
    }


def test_balance_migration_preserves_earned_claims(monkeypatch):
    migration = _load(BALANCE_MIGRATION)
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
        assert len(migration._CATALOG) == 95
        migration.downgrade()
        assert len(connection.execute(sa.select(objectives)).all()) == 95
    engine.dispose()


def test_spine_migration_rebalances_starter_rows_without_touching_claims(monkeypatch):
    migration = _load(SPINE_MIGRATION)
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
        sa.Column("template_key", sa.String()),
    )
    link = sa.Table(
        "vaultobjectiveprogresslink",
        metadata,
        sa.Column("vault_id", sa.Uuid(), primary_key=True),
        sa.Column("objective_id", sa.Uuid(), primary_key=True),
        sa.Column("progress", sa.Integer()),
        sa.Column("total", sa.Integer()),
        sa.Column("is_completed", sa.Boolean()),
        sa.Column("reward_snapshot", sa.String()),
        sa.Column("credited_dweller_ids", sa.JSON()),
    )
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        metadata.create_all(connection)
        identifier = uuid4()
        connection.execute(
            objective.insert().values(
                id=identifier,
                challenge="Assign a dweller correctly",
                reward="50 caps",
                category="starter",
                objective_type="assign_correct",
                target_entity={},
                target_amount=1,
                sequence=3,
                description="Match a dweller's best SPECIAL to the room.",
                template_key="starter:assign a dweller correctly",
            )
        )
        connection.execute(
            link.insert().values(
                vault_id=uuid4(),
                objective_id=identifier,
                progress=1,
                total=1,
                is_completed=True,
                reward_snapshot="50 caps",
                credited_dweller_ids=[],
            )
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        upgraded = sa.MetaData()
        upgraded.reflect(connection)
        objectives, links = upgraded.tables["objective"], upgraded.tables["vaultobjectiveprogresslink"]
        reworded = connection.execute(sa.select(objectives).where(objectives.c.id == identifier)).mappings().one()
        assert reworded["challenge"] == "Match a dweller to their room"
        assert reworded["template_key"] == "starter:assign a dweller correctly"
        assert reworded["sequence"] == 0
        assert len(connection.execute(sa.select(objectives)).all()) == 85
        assert connection.execute(sa.select(links)).mappings().one()["reward_snapshot"] == "50 caps"
        assert _frozen_catalog(migration) == _json_catalog()
        migration.downgrade()
        assert len(connection.execute(sa.select(objectives)).all()) == 85
    engine.dispose()
