"""Chat continuity migration: thread + message link + memory tables, pair-grouped backfill.

Runs the real upgrade/downgrade on SQLite with a minimal legacy ``chatmessage`` (the
fragment-test pattern); the PostgreSQL chain is verified separately with ``alembic heads``
and offline ``--sql`` generation.
"""

import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid7

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[3]
REVISION = "a80944c56929"
MIGRATIONS_DIR = BACKEND / "app/alembic/baseline_versions"


def _load_migration():
    matches = sorted(MIGRATIONS_DIR.glob(f"*-{REVISION}_*.py"))
    if len(matches) != 1:
        raise AssertionError(f"Expected one migration for {REVISION}, found {matches}")
    spec = importlib.util.spec_from_file_location("chat_continuity", matches[0])
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {matches[0]}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration()

U1, U2, D1, D2, V1 = uuid7(), uuid7(), uuid7(), uuid7(), uuid7()
T1 = datetime(2026, 11, 19, 10, 0)
T2 = datetime(2026, 11, 19, 11, 0)
T3 = datetime(2026, 11, 19, 12, 0)
T4 = datetime(2026, 11, 19, 13, 0)
T5 = datetime(2026, 11, 19, 14, 0)

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
    for i, (fu, fd, tu, td, at) in enumerate(rows):
        message_id = uuid7()
        ids[f"m{i}"] = message_id
        connection.execute(
            _INSERT_MESSAGE,
            {
                "id": message_id,
                "vault_id": V1,
                "from_user_id": fu,
                "from_dweller_id": fd,
                "to_user_id": tu,
                "to_dweller_id": td,
                "message_text": f"message {i}",
                "created_at": at,
            },
        )
    return ids


def _install(monkeypatch, connection, *, offline: bool = False) -> None:
    monkeypatch.setattr(MIGRATION, "op", Operations(MigrationContext.configure(connection)))
    monkeypatch.setattr(MIGRATION, "context", SimpleNamespace(is_offline_mode=lambda: offline))


def test_revision_chain_and_single_head() -> None:
    assert MIGRATION.revision == REVISION
    assert MIGRATION.down_revision == "9a73f29c2ed1"
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert script.get_heads() == [REVISION]


def test_upgrade_backfills_one_conversation_per_pair(monkeypatch) -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        ids = _seed_legacy(connection)
        _install(monkeypatch, connection)
        MIGRATION.upgrade()

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
    engine.dispose()


def test_upgrade_empty_history_creates_no_conversations(monkeypatch) -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _create_legacy_tables(connection)
        _install(monkeypatch, connection)
        MIGRATION.upgrade()
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM conversation").scalar_one() == 0
    engine.dispose()


def test_offline_mode_skips_backfill(monkeypatch) -> None:
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        _seed_legacy(connection)
        _install(monkeypatch, connection, offline=True)
        MIGRATION.upgrade()
        assert connection.exec_driver_sql("SELECT COUNT(*) FROM conversation").scalar_one() == 0
        linked = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM chatmessage WHERE conversation_id IS NOT NULL"
        ).scalar_one()
        assert linked == 0
    engine.dispose()
