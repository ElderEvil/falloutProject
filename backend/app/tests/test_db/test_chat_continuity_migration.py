import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid7

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from app.tests.test_alembic._support import load_migration

BACKEND = Path(__file__).resolve().parents[3]
REVISION = "a80944c56929"
MIGRATIONS_DIR = BACKEND / "app/alembic/baseline_versions"
MIGRATION = load_migration(REVISION, "chat_continuity", directory=MIGRATIONS_DIR)

U1, U2, D1, D2, V1 = uuid7(), uuid7(), uuid7(), uuid7(), uuid7()
T1, T2, T3, T4, T5 = (datetime(2026, 11, 19, hour) for hour in (10, 11, 12, 13, 14))

_INSERT_MESSAGE = sa.text(
    "INSERT INTO chatmessage (id, vault_id, from_user_id, from_dweller_id, to_user_id, to_dweller_id,"
    " message_text, created_at) VALUES (:id, :vault_id, :from_user_id, :from_dweller_id, :to_user_id,"
    " :to_dweller_id, :message_text, :created_at)"
).bindparams(
    sa.bindparam("id", type_=sa.UUID),
    sa.bindparam("vault_id", type_=sa.UUID),
    sa.bindparam("from_user_id", type_=sa.UUID),
    sa.bindparam("from_dweller_id", type_=sa.UUID),
    sa.bindparam("to_user_id", type_=sa.UUID),
    sa.bindparam("to_dweller_id", type_=sa.UUID),
    sa.bindparam("created_at", type_=sa.DateTime),
)


def _create_legacy_tables(connection) -> None:
    connection.exec_driver_sql(
        "CREATE TABLE chatmessage (id CHAR(32) PRIMARY KEY, vault_id CHAR(32), from_user_id CHAR(32),"
        " from_dweller_id CHAR(32), to_user_id CHAR(32), to_dweller_id CHAR(32),"
        " message_text VARCHAR(2000), created_at TIMESTAMP)"
    )
    # Minimal FK parents: batch-mode reflection follows conversation's FKs to these tables.
    connection.exec_driver_sql("CREATE TABLE vault (id CHAR(32) PRIMARY KEY)")
    connection.exec_driver_sql('CREATE TABLE "user" (id CHAR(32) PRIMARY KEY)')
    connection.exec_driver_sql("CREATE TABLE dweller (id CHAR(32) PRIMARY KEY)")


def _seed_legacy(connection) -> dict[str, UUID]:
    _create_legacy_tables(connection)
    rows = [
        # Columns: from-user, from-dweller, to-user, to-dweller, timestamp.
        (U1, None, None, D1, T1),
        (None, D1, U1, None, T2),
        (U1, None, None, D1, T3),
        (U1, None, None, D2, T4),
        (None, D1, None, D2, T4),  # dweller-to-dweller: no user pair, stays unlinked
        (U2, None, None, D1, T5),
    ]
    ids = {}
    for i, (from_user, from_dweller, to_user, to_dweller, at) in enumerate(rows):
        message_id = uuid7()
        ids[f"m{i}"] = message_id
        connection.execute(
            _INSERT_MESSAGE,
            {
                "id": message_id,
                "vault_id": V1,
                "from_user_id": from_user,
                "from_dweller_id": from_dweller,
                "to_user_id": to_user,
                "to_dweller_id": to_dweller,
                "message_text": f"message {i}",
                "created_at": at,
            },
        )
    return ids


def _install(connection, *, offline: bool = False) -> None:
    MIGRATION.op = Operations(MigrationContext.configure(connection))
    MIGRATION.context = SimpleNamespace(is_offline_mode=lambda: offline)


def _upgraded(offline: bool = False):
    engine = sa.create_engine("sqlite://")
    connection = engine.connect()
    transaction = connection.begin()
    ids = _seed_legacy(connection)
    _install(connection, offline=offline)
    MIGRATION.upgrade()
    return engine, connection, transaction, ids


def test_revision_chain_and_single_head() -> None:
    assert MIGRATION.revision == REVISION
    assert MIGRATION.down_revision == "9a73f29c2ed1"
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    # The head moves as later migrations land: assert a single head with this revision in the chain.
    heads = script.get_heads()
    assert len(heads) == 1, f"expected one head, got {heads}"
    assert REVISION in {rev.revision for rev in script.walk_revisions()}


def test_upgrade_backfills_one_conversation_per_pair() -> None:
    engine, connection, transaction, ids = _upgraded()
    try:
        conversations = connection.exec_driver_sql(
            "SELECT id, vault_id, user_id, dweller_id, message_count, last_message_at, context FROM conversation"
        ).all()
        assert len(conversations) == 3  # (U1,D1), (U1,D2), (U2,D1) — not one per row
        by_pair = {(row[2], row[3]): row for row in conversations}
        assert set(by_pair) == {(U1.hex, D1.hex), (U1.hex, D2.hex), (U2.hex, D1.hex)}
        assert by_pair[U1.hex, D1.hex][4] == 3
        assert by_pair[U1.hex, D1.hex][5] == "2026-11-19 12:00:00.000000"
        assert by_pair[U1.hex, D2.hex][4] == 1
        assert by_pair[U2.hex, D1.hex][4] == 1
        assert all(row[1] == V1.hex for row in conversations)
        assert all(row[6] is None for row in conversations)
        assert all(UUID(row[0]).version == 7 for row in conversations)
        links = dict(connection.exec_driver_sql("SELECT id, conversation_id FROM chatmessage").all())
        assert links[ids["m0"].hex] == by_pair[U1.hex, D1.hex][0]
        assert links[ids["m1"].hex] == by_pair[U1.hex, D1.hex][0]
        assert links[ids["m2"].hex] == by_pair[U1.hex, D1.hex][0]
        assert links[ids["m3"].hex] == by_pair[U1.hex, D2.hex][0]
        assert links[ids["m4"].hex] is None
        assert links[ids["m5"].hex] == by_pair[U2.hex, D1.hex][0]
        memory_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(dweller_memory)")}
        assert {
            "id",
            "dweller_id",
            "fact",
            "fact_hash",
            "source_message_id",
            "created_at",
            "updated_at",
        } <= memory_columns
        MIGRATION.downgrade()
        tables = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "conversation" not in tables
        assert "dweller_memory" not in tables
        chat_columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(chatmessage)")}
        assert "conversation_id" not in chat_columns
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_upgrade_empty_history_creates_no_conversations() -> None:
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            _create_legacy_tables(connection)
            _install(connection)
            MIGRATION.upgrade()
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM conversation").scalar_one() == 0
    finally:
        engine.dispose()


def test_backfill_never_aggregates_a_uuid_column() -> None:
    # PostgreSQL has no min(uuid)/max(uuid) while SQLite accepts both, so read the SQL directly.
    source = next(MIGRATIONS_DIR.glob(f"*-{REVISION}_*.py")).read_text()
    aggregates = re.findall(r"\b(?:MIN|MAX|SUM|AVG)\s*\(\s*([a-z_]+)\s*\)", source)
    offenders = [column for column in aggregates if column == "id" or column.endswith("_id")]
    assert not offenders, f"aggregate over a uuid column fails on PostgreSQL: {offenders}"


def test_offline_mode_skips_backfill() -> None:
    engine, connection, transaction, _ids = _upgraded(offline=True)
    try:
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM conversation").scalar_one() == 0
        linked = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM chatmessage WHERE conversation_id IS NOT NULL"
        ).scalar_one()
        assert linked == 0
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()
