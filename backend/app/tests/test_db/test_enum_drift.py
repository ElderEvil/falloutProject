from typing import Any

import pytest
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel

import app.models

pytest_plugins = ["app.tests.test_alembic._support"]

# Labels are stored as the StrEnum member NAME (uppercase), not the value.
# Compare against the live PG enum type name (`typname`) and labels (`enumlabel`).
PG_ENUM_LABELS_SNAPSHOT: dict[str, set[str]] = {
    "agegroupenum": {"CHILD", "TEEN", "ADULT", "ELDER"},
    "arenamode": {"DUEL", "BRAWL", "TRAINING", "HUNT"},
    "availabilityenum": {"VAULT", "DEPARTURE", "POOL", "MARKET", "ARCHIVE"},
    "combatzonematchstatus": {"ACTIVE", "FINISHED"},
    "combatzonepartystatus": {"TRAVELING", "QUEUED", "IN_MATCH", "RETURNING", "HOME"},
    "combatzonestance": {"AGGRESSIVE", "DEFENSIVE", "FOCUS", "RETREAT"},
    "craftingorderstatus": {"ACTIVE", "COMPLETED", "COLLECTED", "CANCELLED"},
    "deathcauseenum": {"HEALTH", "RADIATION", "INCIDENT", "EXPLORATION", "COMBAT", "EXILE"},
    "dwellerlocationrelationenum": {"ORIGIN", "VISITED"},
    "dwellerstatusenum": {"IDLE", "WORKING", "EXPLORING", "QUESTING", "TRAINING", "RESTING", "FIGHTING", "DEAD"},
    "expeditionrunstatus": {"IN_ROOM", "RETREATED", "CLEARED", "DIED", "DEFEATED"},
    "explorationstatus": {"ACTIVE", "RETURNING", "COMPLETED", "RECALLED"},
    "genderenum": {"MALE", "FEMALE"},
    "hazardteam": {"FIRE", "RADIATION"},
    "incidentstatus": {"ACTIVE", "SPREADING", "RESOLVED", "FAILED"},
    "incidenttype": {
        "RAIDER_ATTACK",
        "RADROACH_INFESTATION",
        "MOLE_RAT_ATTACK",
        "DEATHCLAW_ATTACK",
        "FERAL_GHOUL_ATTACK",
        "RADSCORPION_ATTACK",
        "FIRE",
    },
    "junktypeenum": {"CIRCUITRY", "LEATHER", "ADHESIVE", "CLOTH", "SCIENCE", "STEEL", "VALUABLES"},
    "lifecycleenum": {"ALIVE", "DEAD_REVIVABLE", "DEAD_PERMANENT", "WASTELAND"},
    "locationtypeenum": {"ORIGIN", "VISITED", "DISCOVERY", "HOME_VAULT"},
    "notificationpriority": {"INFO", "NORMAL", "HIGH", "URGENT"},
    "notificationtype": {
        "EXPLORATION_UPDATE",
        "EXPLORATION_COMPLETE",
        "LEVEL_UP",
        "TRAINING_COMPLETE",
        "TRAINING_STARTED",
        "CRAFTING_COMPLETE",
        "STORAGE_ITEM_DEGRADED",
        "STORAGE_ITEM_UPGRADED",
        "RECIPE_UNLOCKED",
        "RELATIONSHIP_FORMED",
        "PREGNANCY_DETECTED",
        "BABY_BORN",
        "COMBAT_STARTED",
        "COMBAT_VICTORY",
        "COMBAT_DEFEAT",
        "ARENA_MORALE_BOOST",
        "DWELLER_INJURED",
        "DWELLER_DIED",
        "DWELLER_EXIT_REQUESTED",
        "HAZARD_TEAM_JOINED",
        "RESOURCE_LOW",
        "RESOURCE_CRITICAL",
        "POWER_OUTAGE",
        "RUSH_SUCCEEDED",
        "RUSH_FAILED",
        "QUEST_COMPLETE",
        "OBJECTIVE_COMPLETED",
        "OBJECTIVES_REFRESHED",
        "ACHIEVEMENT_UNLOCKED",
        "ROOM_UNLOCKED",
        "RADIO_NEW_DWELLER",
        "RADIO_AUTO_SWITCHED_TO_HAPPINESS",
        "MAP_REGISTRATION_FAILED",
        "COLLECTIBLE_FOUND",
        "LOCATION_CLEARED",
        "LOCATION_READY",
        "WORLD_EVENT_COMPLETED",
    },
    "outfittypeenum": {"COMMON", "RARE", "LEGENDARY", "POWER_ARMOR", "TIERED"},
    "placekind": {"PLACE", "VAULT"},
    "pregnancystatusenum": {"PREGNANT", "DELIVERED", "MISCARRIED"},
    "questtype": {"MAIN", "SIDE", "DAILY", "EVENT", "REPEATABLE"},
    "rarityenum": {"COMMON", "RARE", "LEGENDARY"},
    "relationshiptypeenum": {"ACQUAINTANCE", "FRIEND", "ROMANTIC", "PARTNER", "MARRIED", "RIVAL", "EX"},
    "requirementtype": {"LEVEL", "ITEM", "ROOM", "DWELLER_COUNT", "QUEST_COMPLETED", "ATTACK", "STAT"},
    "rewardtype": {"CAPS", "ITEM", "DWELLER", "RESOURCE", "EXPERIENCE", "STIMPAK", "RADAWAY", "LUNCHBOX"},
    "roomtypeenum": {
        "CAPACITY",
        "CRAFTING",
        "MISC",
        "PRODUCTION",
        "QUESTS",
        "THEME",
        "TRAINING",
        "ARENA",
        "RESPONSE",
    },
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
    "worldeventstatus": {"SCHEDULED", "ACTIVE", "COMPLETED", "EXPIRED"},
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
            if isinstance(column.type, SAEnum) and column.type.name is not None:
                result.setdefault(column.type.name, set()).update(column.type.enums)
    return result


def metadata_enum_columns() -> list[tuple[str, str, Any]]:
    return [
        (table.name, column.name, column.type)
        for table in SQLModel.metadata.tables.values()
        for column in table.c
        if isinstance(column.type, SAEnum)
    ]


class TestPgEnumDrift:
    def test_metadata_enum_columns_match_snapshot(self) -> None:
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
        non_native = [(table, column) for table, column, type_ in metadata_enum_columns() if not type_.native_enum]
        assert not non_native, (
            f"Enum columns with native_enum=False: {non_native}. "
            "Native PG enums are required so enum drift is visible in pg_enum."
        )

    def test_documented_non_native_exceptions_are_still_varchar(self) -> None:
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


def test_expedition_scene_ids_match_manifest_and_enemy_pools():
    import json
    from pathlib import Path

    from app.core.enums import ExpeditionSceneId
    from app.services.catalog_service import SITE_ENEMY_POOLS

    manifest = Path(__file__).resolve().parents[4] / "frontend/src/modules/exploration/models/wasteland-scenes.json"
    assert set(ExpeditionSceneId) == set(SITE_ENEMY_POOLS) == set(json.loads(manifest.read_text()))
