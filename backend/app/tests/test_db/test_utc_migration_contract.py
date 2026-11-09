"""Rehearse the UTC conversion contract without migrating application tables.

PostgreSQL cases use connection-local temporary tables and the existing enum type.
Set UTC_MIGRATION_REQUIRE_POSTGRES=1 to fail rather than skip unavailable PostgreSQL.
These checks are preparation, not a substitute for testing the eventual Alembic revision.
"""

import json
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, MetaData, Table, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.enums import SPECIALEnum
from app.schemas.training import TrainingRead
from app.utils.types import UTCDateTime

INSTANTS = (
    datetime(2026, 1, 15, 12, 34, 56, 123456),
    datetime(2026, 3, 29, 1, 30, 0, 123456),
    datetime(2026, 10, 25, 1, 30, 0, 123456),
    datetime(2024, 2, 29, 23, 59, 59, 999999),
)
ZONES = ("UTC", "Europe/Kyiv", "America/New_York", "Pacific/Chatham")
CONVERT_TO_AWARE = text(
    "ALTER TABLE utc_migration_sample "
    "ALTER COLUMN started_at TYPE timestamptz USING started_at AT TIME ZONE 'UTC', "
    "ALTER COLUMN deadline_at TYPE timestamptz USING deadline_at AT TIME ZONE 'UTC'"
)


@pytest_asyncio.fixture(loop_scope="function")
async def utc_connection() -> AsyncGenerator[AsyncConnection]:
    unavailable = pytest.fail if os.getenv("UTC_MIGRATION_REQUIRE_POSTGRES") == "1" else pytest.skip
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        unavailable("UTC migration rehearsal requires PostgreSQL")
    engine = create_async_engine(uri, poolclass=NullPool, connect_args={"timeout": 5})
    try:
        connection = await engine.connect()
    except OSError, SQLAlchemyError:
        await engine.dispose()
        unavailable("PostgreSQL unavailable for UTC migration rehearsal")

    try:
        async with connection.begin():
            await connection.execute(
                text(
                    "CREATE TEMP TABLE utc_migration_sample ("
                    "id integer PRIMARY KEY, started_at timestamp NOT NULL, deadline_at timestamp, "
                    "payload jsonb NOT NULL, status explorationstatus NOT NULL) ON COMMIT DROP"
                )
            )
            yield connection
    finally:
        await connection.close()
        await engine.dispose()


async def seed_sample(connection: AsyncConnection, instant: datetime) -> dict[str, list[dict[str, str]]]:
    payload = {"events": [{"timestamp": instant.isoformat()}], "loot": [{"found_at": instant.isoformat()}]}
    await connection.execute(
        text(
            "INSERT INTO utc_migration_sample VALUES "
            "(1, :started, :deadline, CAST(:payload AS jsonb), 'ACTIVE'), "
            "(2, :started, NULL, CAST(:payload AS jsonb), 'COMPLETED')"
        ),
        {"started": instant, "deadline": instant + timedelta(hours=1), "payload": json.dumps(payload)},
    )
    return payload


@pytest.mark.integration
async def test_timestamp_inventory_matches_migrated_schema(utc_connection: AsyncConnection) -> None:
    expected = {
        (table.name, column.name): True
        for table in SQLModel.metadata.tables.values()
        for column in table.c
        if isinstance(column.type, UTCDateTime)
    }
    assert len(expected) == 122
    assert len({table for table, _ in expected}) == 39
    rows = await utc_connection.execute(
        text(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema='public' AND data_type IN "
            "('timestamp without time zone', 'timestamp with time zone')"
        )
    )
    actual = {(table, column): kind == "timestamp with time zone" for table, column, kind in rows}
    assert actual == expected
    assert actual, "The inventory must inspect a migrated application schema"


@pytest.mark.integration
@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize("instant", INSTANTS)
async def test_explicit_utc_conversion_preserves_instants_nulls_and_payloads(
    utc_connection: AsyncConnection, zone: str, instant: datetime
) -> None:
    await utc_connection.execute(text("SELECT set_config('TimeZone', :zone, true)"), {"zone": zone})
    payload = await seed_sample(utc_connection, instant)
    await utc_connection.execute(CONVERT_TO_AWARE)

    rows = (await utc_connection.execute(text("SELECT * FROM utc_migration_sample ORDER BY id"))).mappings().all()
    expected = instant.replace(tzinfo=UTC)
    assert rows[0]["started_at"] == expected
    assert rows[0]["started_at"].utcoffset() == timedelta(0)
    assert rows[0]["deadline_at"] == expected + timedelta(hours=1)
    assert rows[1]["deadline_at"] is None
    assert [row["status"] for row in rows] == ["ACTIVE", "COMPLETED"]
    assert all(row["payload"] == payload for row in rows)


@pytest.mark.integration
async def test_implicit_conversion_would_shift_legacy_utc(utc_connection: AsyncConnection) -> None:
    instant = INSTANTS[0]
    await utc_connection.execute(text("SET LOCAL TIME ZONE 'Europe/Kyiv'"))
    await seed_sample(utc_connection, instant)
    await utc_connection.execute(text("ALTER TABLE utc_migration_sample ALTER COLUMN started_at TYPE timestamptz"))
    converted = (
        await utc_connection.execute(text("SELECT started_at FROM utc_migration_sample WHERE id=1"))
    ).scalar_one()
    assert converted != instant.replace(tzinfo=UTC)
    assert converted == instant.replace(tzinfo=ZoneInfo("Europe/Kyiv")).astimezone(UTC)


@pytest.mark.integration
@pytest.mark.parametrize("zone", ZONES)
async def test_deadline_boundary_matches_before_and_after_conversion(
    utc_connection: AsyncConnection, zone: str
) -> None:
    await utc_connection.execute(text("SELECT set_config('TimeZone', :zone, true)"), {"zone": zone})
    now = INSTANTS[2]
    for identifier, delta in enumerate((-1, 0, 1), start=1):
        await utc_connection.execute(
            text("INSERT INTO utc_migration_sample VALUES (:id, :now, :deadline, '{}', 'ACTIVE')"),
            {"id": identifier, "now": now, "deadline": now + timedelta(microseconds=delta)},
        )
    before = await utc_connection.execute(
        text("SELECT id FROM utc_migration_sample WHERE deadline_at <= :now ORDER BY id"), {"now": now}
    )
    assert before.scalars().all() == [1, 2]
    await utc_connection.execute(CONVERT_TO_AWARE)
    after = await utc_connection.execute(
        text("SELECT id FROM utc_migration_sample WHERE deadline_at <= CAST(:now AS timestamptz) ORDER BY id"),
        {"now": now.replace(tzinfo=UTC)},
    )
    assert after.scalars().all() == [1, 2]


@pytest.mark.integration
async def test_late_failure_rolls_back_conversion_and_preserves_rows(utc_connection: AsyncConnection) -> None:
    await utc_connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
    await seed_sample(utc_connection, INSTANTS[0])
    before = (await utc_connection.execute(text("SELECT * FROM utc_migration_sample ORDER BY id"))).all()
    savepoint = await utc_connection.begin_nested()
    await utc_connection.execute(CONVERT_TO_AWARE)
    with pytest.raises(IntegrityError):
        await utc_connection.execute(text("INSERT INTO utc_migration_sample SELECT * FROM utc_migration_sample"))
    await savepoint.rollback()
    after = (await utc_connection.execute(text("SELECT * FROM utc_migration_sample ORDER BY id"))).all()
    assert after == before
    assert after[0].started_at.tzinfo is None
    assert (
        await utc_connection.execute(text("SELECT pg_typeof(started_at)::text FROM utc_migration_sample LIMIT 1"))
    ).scalar_one() == "timestamp without time zone"


@pytest.mark.integration
async def test_reverse_expression_recovers_naive_utc_after_offset_aware_write(utc_connection: AsyncConnection) -> None:
    await utc_connection.execute(text("SET LOCAL TIME ZONE 'Pacific/Chatham'"))
    await seed_sample(utc_connection, INSTANTS[0])
    await utc_connection.execute(CONVERT_TO_AWARE)
    instant = INSTANTS[1].replace(tzinfo=UTC)
    offset_value = instant.astimezone(timezone(timedelta(hours=5, minutes=45)))
    await utc_connection.execute(
        text("INSERT INTO utc_migration_sample VALUES (3, :started, NULL, '{}', 'ACTIVE')"), {"started": offset_value}
    )
    await utc_connection.execute(
        text(
            "ALTER TABLE utc_migration_sample "
            "ALTER COLUMN started_at TYPE timestamp USING started_at AT TIME ZONE 'UTC', "
            "ALTER COLUMN deadline_at TYPE timestamp USING deadline_at AT TIME ZONE 'UTC'"
        )
    )
    rows = (
        await utc_connection.execute(text("SELECT started_at, deadline_at FROM utc_migration_sample ORDER BY id"))
    ).all()
    assert rows[0] == (INSTANTS[0], INSTANTS[0] + timedelta(hours=1))
    assert rows[1] == (INSTANTS[0], None)
    assert rows[2] == (instant.replace(tzinfo=None), None)


@pytest.mark.parametrize("offset", [None, UTC, timezone(timedelta(hours=5, minutes=45)), timezone(-timedelta(hours=4))])
@pytest.mark.parametrize("completed", [False, True], ids=["pending", "completed"])
def test_training_wire_contract_keeps_utc_instant_and_nullable_completion(
    offset: timezone | None, completed: bool
) -> None:
    instant = INSTANTS[0].replace(tzinfo=UTC)
    value = instant.replace(tzinfo=None) if offset is None else instant.astimezone(offset)
    payload = {
        "id": str(uuid4()),
        "dweller_id": str(uuid4()),
        "vault_id": str(uuid4()),
        "stat_being_trained": SPECIALEnum.STRENGTH,
        "current_stat_value": 1,
        "target_stat_value": 2,
        "started_at": value.isoformat(),
        "estimated_completion_at": (value + timedelta(hours=1)).isoformat(),
        "created_at": value.isoformat(),
        "updated_at": value.isoformat(),
        "completed_at": (value + timedelta(hours=1)).isoformat() if completed else None,
    }
    schema = TrainingRead.model_validate(payload)
    wire = schema.model_dump(mode="json")
    assert wire["started_at"] == "2026-01-15T12:34:56.123456Z"
    assert wire["estimated_completion_at"] == "2026-01-15T13:34:56.123456Z"
    assert wire["created_at"] == wire["updated_at"] == wire["started_at"]
    assert wire["completed_at"] == ("2026-01-15T13:34:56.123456Z" if completed else None)
    restored = TrainingRead.model_validate_json(schema.model_dump_json())
    assert restored.started_at == instant
    assert restored.completed_at == (instant + timedelta(hours=1) if completed else None)


@pytest.mark.integration
async def test_utc_datetime_type_round_trips_on_postgres(utc_connection: AsyncConnection) -> None:
    """UTCDateTime binds explicit offsets and reads back the same UTC instant on PostgreSQL."""
    metadata = MetaData()
    table = Table(
        "utc_type_round_trip",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("ts", UTCDateTime, nullable=False),
        prefixes=["TEMPORARY"],
    )
    await utc_connection.run_sync(metadata.create_all)
    instant = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    offset_value = instant.astimezone(timezone(timedelta(hours=5, minutes=45)))
    await utc_connection.execute(table.insert().values(id=1, ts=offset_value))

    row = (await utc_connection.execute(table.select())).one()
    assert row.ts == instant
    assert row.ts.utcoffset() == timedelta(0)

    result = await utc_connection.execute(table.select().where(table.c.ts <= instant + timedelta(minutes=15)))
    assert result.one().id == 1
