"""Regression tests guarding PostgreSQL enum labels against Python StrEnum drift.

History: a Python StrEnum member (``DWELLER_DIED``) was added to
``NotificationType`` without a matching Alembic migration. The live
PostgreSQL enum type ``notificationtype`` was missing the label, causing
``InvalidTextRepresentationError`` on write → poisoned connection pool →
worker crash-loop in production (see AGENTS.md "DB Enums & Alembic Migrations").

Alembic autogenerate does NOT reliably detect enum value changes, so this
module pins the expected label sets in two independent layers:

1. ``test_metadata_enum_columns_match_snapshot`` — CI-safe (no DB needed):
   compares the labels derived from the SQLAlchemy model metadata against a
   golden snapshot. Catches Python-side drift: a member added/removed/renamed
   in a StrEnum without a corresponding migration + snapshot update.

2. ``test_live_pg_enum_labels_match_metadata`` — runs only when a live
   PostgreSQL database is reachable (skips otherwise, e.g. the SQLite-based
   CI suite): compares ``pg_enum`` catalog labels against the model metadata.
   Catches DB-side drift: a migration written but never applied.

Golden snapshot maintenance: update ``PG_ENUM_LABELS_SNAPSHOT`` in the SAME
commit that writes an ``ALTER TYPE ... ADD/RENAME VALUE`` migration (see
AGENTS.md for the manual migration procedure).
"""

from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import Enum as SAEnum
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

import app.models
from app.core.config import settings

# Labels are stored as the StrEnum member NAME (uppercase), not the value.
# Compare against the live PG enum type name (`typname`) and labels (`enumlabel`).
PG_ENUM_LABELS_SNAPSHOT: dict[str, set[str]] = {
    "agegroupenum": {"CHILD", "TEEN", "ADULT"},
    "deathcauseenum": {"HEALTH", "RADIATION", "INCIDENT", "EXPLORATION", "COMBAT"},
    "dwellerlocationrelationenum": {"ORIGIN", "VISITED"},
    "dwellerstatusenum": {"IDLE", "WORKING", "EXPLORING", "QUESTING", "TRAINING", "RESTING", "DEAD"},
    "explorationstatus": {"ACTIVE", "COMPLETED", "RECALLED"},
    "genderenum": {"MALE", "FEMALE"},
    "incidentstatus": {"ACTIVE", "SPREADING", "RESOLVED", "FAILED"},
    "incidenttype": {
        "RAIDER_ATTACK",
        "RADROACH_INFESTATION",
        "MOLE_RAT_ATTACK",
        "DEATHCLAW_ATTACK",
        "FERAL_GHOUL_ATTACK",
        "FIRE",
    },
    "junktypeenum": {"CIRCUITRY", "LEATHER", "ADHESIVE", "CLOTH", "SCIENCE", "STEEL", "VALUABLES"},
    "locationtypeenum": {"ORIGIN", "VISITED", "DISCOVERY", "HOME_VAULT"},
    "notificationpriority": {"INFO", "NORMAL", "HIGH", "URGENT"},
    "notificationtype": {
        "EXPLORATION_UPDATE",
        "EXPLORATION_COMPLETE",
        "LEVEL_UP",
        "TRAINING_COMPLETE",
        "TRAINING_STARTED",
        "RELATIONSHIP_FORMED",
        "PREGNANCY_DETECTED",
        "BABY_BORN",
        "COMBAT_STARTED",
        "COMBAT_VICTORY",
        "COMBAT_DEFEAT",
        "DWELLER_INJURED",
        "DWELLER_DIED",
        "RESOURCE_LOW",
        "RESOURCE_CRITICAL",
        "POWER_OUTAGE",
        "QUEST_COMPLETE",
        "ACHIEVEMENT_UNLOCKED",
        "RADIO_NEW_DWELLER",
        "MAP_REGISTRATION_FAILED",
    },
    "outfittypeenum": {"COMMON", "RARE", "LEGENDARY", "POWER_ARMOR", "TIERED"},
    "pregnancystatusenum": {"PREGNANT", "DELIVERED", "MISCARRIED"},
    "questtype": {"MAIN", "SIDE", "DAILY", "EVENT", "REPEATABLE"},
    "rarityenum": {"COMMON", "RARE", "LEGENDARY"},
    "relationshiptypeenum": {"ACQUAINTANCE", "FRIEND", "ROMANTIC", "PARTNER", "MARRIED", "EX"},
    "requirementtype": {"LEVEL", "ITEM", "ROOM", "DWELLER_COUNT", "QUEST_COMPLETED"},
    "rewardtype": {"CAPS", "ITEM", "DWELLER", "RESOURCE", "EXPERIENCE", "STIMPAK", "RADAWAY", "LUNCHBOX"},
    "roomtypeenum": {"CAPACITY", "CRAFTING", "MISC", "PRODUCTION", "QUESTS", "THEME", "TRAINING", "ARENA"},
    "specialenum": {"STRENGTH", "PERCEPTION", "ENDURANCE", "CHARISMA", "INTELLIGENCE", "AGILITY", "LUCK"},
    "trainingstatus": {"ACTIVE", "COMPLETED", "CANCELLED"},
    "weaponsubtypeenum": {
        "BLUNT",
        "EDGED",
        "POINTED",
        "PISTOL",
        "RIFLE",
        "SHOTGUN",
        "AUTOMATIC",
        "EXPLOSIVE",
        "FLAMER",
    },
    "weapontypeenum": {"MELEE", "GUN", "ENERGY", "HEAVY"},
}

# Deliberate non-native exceptions: StrEnum-annotated fields stored as plain
# VARCHAR rather than a PostgreSQL enum type (no pg_enum entry exists).
NON_NATIVE_ENUM_COLUMNS: set[tuple[str, str]] = {
    ("objective", "category"),  # ObjectiveBase.category: Column(String(50))
}


def metadata_enum_map() -> dict[str, set[str]]:
    """Map PostgreSQL enum type name → label set from SQLAlchemy model metadata."""
    result: dict[str, set[str]] = {}
    for table in SQLModel.metadata.tables.values():
        for column in table.c:
            if isinstance(column.type, SAEnum):
                result.setdefault(column.type.name, set()).update(column.type.enums)
    return result


def metadata_enum_columns() -> list[tuple[str, str, Any]]:
    """Return (table, column, type) for every Enum-typed column in the metadata."""
    return [
        (table.name, column.name, column.type)
        for table in SQLModel.metadata.tables.values()
        for column in table.c
        if isinstance(column.type, SAEnum)
    ]


class TestPgEnumDrift:
    """Guard Python StrEnum members against PostgreSQL enum label drift."""

    def test_metadata_enum_columns_match_snapshot(self) -> None:
        """Model-derived enum labels must exactly match the golden snapshot.

        Fails when a StrEnum member is added/removed/renamed without the
        snapshot (and the matching Alembic migration) being updated — the
        exact class of bug that caused the ``DWELLER_DIED`` outage.
        """
        actual = metadata_enum_map()
        missing_from_metadata = set(PG_ENUM_LABELS_SNAPSHOT) - set(actual)
        missing_from_snapshot = set(actual) - set(PG_ENUM_LABELS_SNAPSHOT)
        assert not missing_from_metadata, (
            f"Enum types in snapshot but not in model metadata: {sorted(missing_from_metadata)}. "
            "If the enum class was removed, update the snapshot too."
        )
        assert not missing_from_snapshot, (
            f"Enum types in model metadata but not in snapshot: {sorted(missing_from_snapshot)}. "
            "New native enum columns require a migration AND a snapshot update."
        )
        for type_name, expected in PG_ENUM_LABELS_SNAPSHOT.items():
            assert actual[type_name] == expected, (
                f"Label drift for PG enum type {type_name!r}: "
                f"model metadata has {sorted(actual[type_name])}, snapshot expects {sorted(expected)}. "
                "A StrEnum member changed without a matching ALTER TYPE migration + snapshot update."
            )

    def test_all_native_enum_columns_are_native(self) -> None:
        """Every Enum-typed column must be a native PG enum.

        Guards against an Enum silently degrading to a VARCHAR+CHECK column
        (``native_enum=False``), which would bypass the pg_enum catalog the
        migration procedure is based on.
        """
        non_native = [(table, column) for table, column, type_ in metadata_enum_columns() if not type_.native_enum]
        assert not non_native, (
            f"Enum columns with native_enum=False: {non_native}. "
            "Native PG enums are required so enum drift is visible in pg_enum."
        )

    def test_documented_non_native_exceptions_are_still_varchar(self) -> None:
        """The documented VARCHAR exceptions must not have been converted to enums."""
        from sqlalchemy import String

        for table_name, column_name in sorted(NON_NATIVE_ENUM_COLUMNS):
            table = SQLModel.metadata.tables.get(table_name)
            assert table is not None, f"Non-native exception table {table_name!r} not found"
            column = table.c.get(column_name)
            assert column is not None, f"Non-native exception column {table_name}.{column_name} not found"
            assert not isinstance(column.type, SAEnum), (
                f"{table_name}.{column_name} was a deliberate VARCHAR enum but is now an Enum type; "
                "update NON_NATIVE_ENUM_COLUMNS if this was intentional."
            )
            assert isinstance(column.type, String), (
                f"{table_name}.{column_name} is not a VARCHAR; got {column.type!r}. "
                "Update NON_NATIVE_ENUM_COLUMNS if this was intentional."
            )


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    """Connect to the live PostgreSQL database for the pg_enum catalog check.

    Skips when the configured URI is not PostgreSQL or the database is
    unreachable (e.g. the SQLite-based CI suite). Read-only catalog query.
    """
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping live pg_enum check")

    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    return engine


async def _live_pg_enum_map(engine: AsyncEngine) -> dict[str, set[str]]:
    """Query pg_type + pg_enum for every enum type and its labels."""
    query = text(
        """
        SELECT t.typname, e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typtype = 'e'
        ORDER BY t.typname, e.enumsortorder
        """
    )
    result: dict[str, set[str]] = {}
    async with engine.connect() as conn:
        rows = await conn.execute(query)
        for type_name, label in rows:
            result.setdefault(type_name, set()).add(label)
    return result


class TestLivePgEnumSync:
    """Compare live PostgreSQL pg_enum labels against the model metadata."""

    @pytest.mark.asyncio
    async def test_live_pg_enum_labels_match_metadata(self, live_pg_engine: AsyncEngine) -> None:
        expected = metadata_enum_map()
        live = await _live_pg_enum_map(live_pg_engine)

        missing_types = set(expected) - set(live)
        assert not missing_types, (
            f"PG enum types missing from the live database: {sorted(missing_types)}. Run `uv run alembic upgrade head`."
        )
        for type_name, expected_labels in expected.items():
            live_labels = live.get(type_name, set())
            assert live_labels == expected_labels, (
                f"Live PG enum {type_name!r} drifted from model metadata: "
                f"DB has {sorted(live_labels)}, model metadata expects {sorted(expected_labels)}. "
                "A migration is missing or the DB enum was modified manually."
            )
