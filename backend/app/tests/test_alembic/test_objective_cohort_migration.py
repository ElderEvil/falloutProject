"""Corrective cohort migration: restore legacy starter rows and version the revised ones."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

VERSIONS = Path(__file__).parents[2] / "alembic/versions"
SPINE_MIGRATION = "2026_10_14_0001-e5c2b7f19a04_spine_starter_objectives.py"
CORRECTIVE_MIGRATION = "2026_10_14_0002-f6a1b2c3d4e5_restore_legacy_starter_cohort.py"

STAFFING = "starter:assign a dweller correctly"
POWER_STEP = "starter:collect 150 power"


def _load(filename):
    spec = importlib.util.spec_from_file_location(filename, VERSIONS / filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _schema():
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
    return metadata, objective, link


def test_corrective_migration_restores_legacy_and_versions_revised(monkeypatch):
    spine = _load(SPINE_MIGRATION)
    corrective = _load(CORRECTIVE_MIGRATION)
    metadata, objective, link = _schema()
    engine = sa.create_engine("sqlite://")

    with engine.begin() as connection:
        metadata.create_all(connection)

        identifiers = {}
        for entry in corrective._LEGACY:
            identifier = uuid4()
            identifiers[entry["template_key"]] = identifier
            connection.execute(objective.insert().values(id=identifier, **entry))

        connection.execute(
            link.insert().values(
                vault_id=uuid4(),
                objective_id=identifiers[POWER_STEP],
                progress=5,
                total=150,
                is_completed=False,
                reward_snapshot=None,
                credited_dweller_ids=[],
            )
        )
        connection.execute(
            link.insert().values(
                vault_id=uuid4(),
                objective_id=identifiers[STAFFING],
                progress=1,
                total=1,
                is_completed=True,
                reward_snapshot="50 caps",
                credited_dweller_ids=[],
            )
        )

        monkeypatch.setattr(spine, "op", Operations(MigrationContext.configure(connection)))
        spine.upgrade()
        monkeypatch.setattr(corrective, "op", Operations(MigrationContext.configure(connection)))
        corrective.upgrade()

        upgraded = sa.MetaData()
        upgraded.reflect(connection)
        objectives, links = upgraded.tables["objective"], upgraded.tables["vaultobjectiveprogresslink"]
        by_key = {
            row["template_key"]: row
            for row in connection.execute(sa.select(objectives)).mappings().all()
        }

        restored = connection.execute(
            sa.select(objectives).where(objectives.c.id == identifiers[STAFFING])
        ).mappings().one()
        assert restored["challenge"] == "Assign a dweller correctly"
        assert restored["sequence"] == 3
        assert not restored["assignable"]

        versioned = by_key[f"{STAFFING}#v2"]
        assert versioned["challenge"] == "Match a dweller to their room"
        assert versioned["sequence"] == 0
        assert versioned["assignable"]

        withdrawn = connection.execute(
            sa.select(objectives).where(objectives.c.id == identifiers[POWER_STEP])
        ).mappings().one()
        assert withdrawn["objective_type"] == "collect"
        assert withdrawn["sequence"] == 1
        assert not withdrawn["assignable"]

        partial = connection.execute(
            sa.select(links).where(links.c.objective_id == identifiers[POWER_STEP])
        ).mappings().one()
        assert partial["progress"] == 5
        assert partial["total"] == 150
        assert not partial["is_completed"]

        earned = connection.execute(
            sa.select(links).where(links.c.objective_id == identifiers[STAFFING])
        ).mappings().one()
        assert earned["is_completed"]
        assert earned["reward_snapshot"] == "50 caps"

        assignable = connection.execute(
            sa.select(objectives.c.template_key).where(
                objectives.c.assignable.is_(True), objectives.c.category == "starter"
            )
        ).scalars().all()
        assert len(assignable) == 11

        corrective.upgrade()
        rerun = connection.execute(
            sa.select(objectives.c.template_key).where(
                objectives.c.assignable.is_(True), objectives.c.category == "starter"
            )
        ).scalars().all()
        assert sorted(rerun) == sorted(assignable)

    engine.dispose()
