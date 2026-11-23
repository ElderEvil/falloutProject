import json
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa

from app.tests.test_alembic._support import bind_op, load_migration, sqlite_db

OBJECTIVES = Path(__file__).parents[2] / "data/objectives"
BALANCE_MIGRATION = "2026_10_13_0003-d4b9f62ce731_balance_objectives.py"
SPINE_MIGRATION = "2026_10_14_0001-e5c2b7f19a04_spine_starter_objectives.py"


def _schema(*, migrated: bool) -> tuple[sa.MetaData, sa.Table, sa.Table]:
    metadata = sa.MetaData()
    objective_columns = [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("challenge", sa.String()),
        sa.Column("reward", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("objective_type", sa.String()),
        sa.Column("target_entity", sa.JSON()),
        sa.Column("target_amount", sa.Integer()),
        sa.Column("sequence", sa.Integer()),
        sa.Column("description", sa.String()),
    ]
    link_columns = [
        sa.Column("vault_id", sa.Uuid(), primary_key=True),
        sa.Column("objective_id", sa.Uuid(), primary_key=True),
        sa.Column("progress", sa.Integer()),
        sa.Column("total", sa.Integer()),
        sa.Column("is_completed", sa.Boolean()),
    ]
    if migrated:
        objective_columns.append(sa.Column("template_key", sa.String()))
        link_columns += [sa.Column("reward_snapshot", sa.String()), sa.Column("credited_dweller_ids", sa.JSON())]
    objective = sa.Table("objective", metadata, *objective_columns)
    link = sa.Table("vaultobjectiveprogresslink", metadata, *link_columns)
    return metadata, objective, link


def _reflect(connection):
    upgraded = sa.MetaData()
    upgraded.reflect(connection)
    return upgraded.tables["objective"], upgraded.tables["vaultobjectiveprogresslink"]


def test_balance_migration_preserves_earned_claims():
    migration = load_migration(BALANCE_MIGRATION, BALANCE_MIGRATION)
    metadata, objective, link = _schema(migrated=False)
    with sqlite_db() as connection:
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
        bind_op(migration, connection)
        migration.upgrade()
        objectives, links = _reflect(connection)
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


def test_spine_migration_rebalances_starter_rows_without_touching_claims():
    migration = load_migration(SPINE_MIGRATION, SPINE_MIGRATION)
    metadata, objective, link = _schema(migrated=True)
    with sqlite_db() as connection:
        metadata.create_all(connection)
        identifier, retired_id, custom_id = uuid4(), uuid4(), uuid4()
        rows = (
            {
                "id": identifier,
                "challenge": "Assign a dweller correctly",
                "reward": "50 caps",
                "category": "starter",
                "objective_type": "assign_correct",
                "target_entity": {},
                "target_amount": 1,
                "sequence": 3,
                "description": "Match a dweller's best SPECIAL to the room.",
                "template_key": "starter:assign a dweller correctly",
            },
            {
                "id": retired_id,
                "challenge": "Collect 150 Power",
                "reward": "50 power",
                "category": "starter",
                "objective_type": "collect",
                "target_entity": {"resource_type": "power"},
                "target_amount": 150,
                "sequence": 4,
                "description": "Retired orientation step.",
                "template_key": "starter:collect 150 power",
            },
            {
                "id": custom_id,
                "challenge": "My custom starter",
                "reward": "10 caps",
                "category": "starter",
                "objective_type": "collect",
                "target_entity": {"resource_type": "caps"},
                "target_amount": 5,
                "sequence": None,
                "description": "A template this release did not withdraw.",
                "template_key": "starter:my custom starter",
            },
        )
        for row in rows:
            connection.execute(objective.insert().values(**row))
        for objective_id, progress, total, completed, snapshot in (
            (identifier, 1, 1, True, "50 caps"),
            (retired_id, 5, 150, False, None),
        ):
            connection.execute(
                link.insert().values(
                    vault_id=uuid4(),
                    objective_id=objective_id,
                    progress=progress,
                    total=total,
                    is_completed=completed,
                    reward_snapshot=snapshot,
                    credited_dweller_ids=[],
                )
            )
        bind_op(migration, connection)
        migration.upgrade()
        objectives, links = _reflect(connection)

        def one(table, key, value):
            return connection.execute(sa.select(table).where(table.c[key] == value)).mappings().one()

        reworded = one(objectives, "id", identifier)
        assert reworded["challenge"] == "Match a dweller to their room"
        assert reworded["template_key"] == "starter:assign a dweller correctly"
        assert reworded["sequence"] == 0
        retired = one(objectives, "id", retired_id)
        assert retired["objective_type"] is None
        assert retired["sequence"] is None
        assert one(links, "objective_id", retired_id)["progress"] == 5
        custom = one(objectives, "id", custom_id)
        assert custom["objective_type"] == "collect"
        assert len(connection.execute(sa.select(objectives)).all()) == 95
        assert one(links, "objective_id", identifier)["reward_snapshot"] == "50 caps"
        migration.upgrade()
        assert len(connection.execute(sa.select(objectives)).all()) == 95
        migration.downgrade()
        assert len(connection.execute(sa.select(objectives)).all()) == 95
        # Historical migrations are compared with their frozen release snapshot.
        by_key = {row["template_key"]: row for row in connection.execute(sa.select(objectives)).mappings()}
        for snapshot in migration._CATALOG:
            expected = {field: value for field, value in snapshot.items() if field != "legacy_challenge"}
            assert {field: by_key[expected["template_key"]][field] for field in expected} == expected
        clarification = load_migration(
            "2026_10_16_0003-d8e4c7a2b915_clarify_starter_scrap_objective.py", "clarify_starter_scrap"
        )
        bind_op(clarification, connection)
        clarification.upgrade()
        by_key = {row["template_key"]: row for row in connection.execute(sa.select(objectives)).mappings()}
        assert by_key["starter:reverse-engineer a schematic"]["challenge"] == "Scrap a rare weapon"
