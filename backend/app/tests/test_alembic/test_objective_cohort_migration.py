import json
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.script import ScriptDirectory

from app.tests.test_alembic._support import VERSIONS, bind_op, load_migration, sqlite_db

SPINE_MIGRATION = "2026_10_14_0001-e5c2b7f19a04_spine_starter_objectives.py"
CORRECTIVE_MIGRATION = "2026_10_14_0002-f6a1b2c3d4e5_restore_legacy_starter_cohort.py"
RETIRE_RADIO_MIGRATION = "2026_10_24_1001-d6e8f0a2b4c9_retire_staff_radio_objective.py"

STAFFING = "starter:assign a dweller correctly"
POWER_STEP = "starter:collect 150 power"
RADIO_STEP = "starter:staff the radio"


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
        sa.Column("assignable", sa.Boolean(), server_default=sa.true()),
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


def test_corrective_migration_restores_legacy_and_versions_revised():
    spine = load_migration(SPINE_MIGRATION, "spine_starter_objectives")
    corrective = load_migration(CORRECTIVE_MIGRATION, "restore_legacy_starter_cohort")
    metadata, objective, link = _schema()
    with sqlite_db() as connection:
        metadata.create_all(connection)
        identifiers = {}
        for entry in corrective._LEGACY:
            identifier = uuid4()
            identifiers[entry["template_key"]] = identifier
            connection.execute(objective.insert().values(id=identifier, **entry))
        for key, progress, total, completed, snapshot in (
            (POWER_STEP, 5, 150, False, None),
            (STAFFING, 1, 1, True, "50 caps"),
        ):
            connection.execute(
                link.insert().values(
                    vault_id=uuid4(),
                    objective_id=identifiers[key],
                    progress=progress,
                    total=total,
                    is_completed=completed,
                    reward_snapshot=snapshot,
                    credited_dweller_ids=[],
                )
            )
        bind_op(spine, connection)
        spine.upgrade()
        bind_op(corrective, connection)
        corrective.upgrade()
        upgraded = sa.MetaData()
        upgraded.reflect(connection)
        objectives, links = upgraded.tables["objective"], upgraded.tables["vaultobjectiveprogresslink"]
        by_key = {row["template_key"]: row for row in connection.execute(sa.select(objectives)).mappings().all()}

        def linked(objective_id):
            return connection.execute(sa.select(links).where(links.c.objective_id == objective_id)).mappings().one()

        restored = (
            connection.execute(sa.select(objectives).where(objectives.c.id == identifiers[STAFFING])).mappings().one()
        )
        assert restored["challenge"] == "Assign a dweller correctly"
        assert restored["sequence"] == 3
        assert not restored["assignable"]
        versioned = by_key[f"{STAFFING}#v2"]
        assert versioned["challenge"] == "Match a dweller to their room"
        assert versioned["sequence"] == 0
        assert versioned["assignable"]
        withdrawn = (
            connection.execute(sa.select(objectives).where(objectives.c.id == identifiers[POWER_STEP])).mappings().one()
        )
        assert withdrawn["objective_type"] == "collect"
        assert withdrawn["sequence"] == 1
        assert not withdrawn["assignable"]
        partial = linked(identifiers[POWER_STEP])
        assert partial["progress"] == 5
        assert partial["total"] == 150
        assert not partial["is_completed"]
        earned = linked(identifiers[STAFFING])
        assert earned["is_completed"]
        assert earned["reward_snapshot"] == "50 caps"

        def assignable_keys():
            return (
                connection.execute(
                    sa.select(objectives.c.template_key).where(
                        objectives.c.assignable.is_(True), objectives.c.category == "starter"
                    )
                )
                .scalars()
                .all()
            )

        assignable = assignable_keys()
        assert len(assignable) == 11
        corrective.upgrade()
        assert sorted(assignable_keys()) == sorted(assignable)


def test_retire_radio_migration_stops_fresh_assignment():
    migration = load_migration(RETIRE_RADIO_MIGRATION, "retire_staff_radio_objective")
    metadata, objective, _ = _schema()
    with sqlite_db() as connection:
        metadata.create_all(connection)
        identifier = uuid4()
        connection.execute(
            objective.insert().values(
                id=identifier,
                template_key=RADIO_STEP,
                challenge="Staff the Radio Studio",
                category="starter",
                objective_type="assign",
                target_amount=1,
                sequence=12,
                assignable=True,
            )
        )
        bind_op(migration, connection)
        migration.upgrade()
        assert not connection.execute(
            sa.select(objective.c.assignable).where(objective.c.id == identifier)
        ).scalar_one()
        migration.downgrade()
        assert connection.execute(sa.select(objective.c.assignable).where(objective.c.id == identifier)).scalar_one()


def test_migration_graph_has_one_upgrade_head():
    scripts = ScriptDirectory(str(VERSIONS.parent))
    assert len(scripts.get_heads()) == 1, scripts.get_heads()


def test_retired_radio_keeps_legacy_starter_sequence_positions():
    starters = json.loads((Path(__file__).parents[1] / "data/starter_pre_continuity.json").read_text())
    by_key = {step["template_key"]: step["sequence"] for step in starters}
    assert RADIO_STEP not in by_key
    # Existing vaults retain the radio at 12; catalog sync must not move other steps onto it.
    assert by_key["starter:reach 16 dwellers"] == 13
    assert by_key["starter:reach 18 dwellers"] == 14
    assert by_key["starter:grow a 50-dweller vault"] == 20
