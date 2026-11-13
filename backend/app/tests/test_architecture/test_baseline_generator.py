"""Regression coverage for the baseline generator's safety and recovery paths."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / "scripts/build_alembic_baseline.py"
SPEC = importlib.util.spec_from_file_location("build_alembic_baseline", SCRIPT)
assert SPEC
assert SPEC.loader
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


@pytest.mark.parametrize("direct", [True, False])
@pytest.mark.parametrize("program", ["psql", "pg_dump"])
def test_client_preserves_connection_and_output_options(
    monkeypatch: pytest.MonkeyPatch, direct: bool, program: str
) -> None:
    monkeypatch.setattr(GENERATOR.shutil, "which", lambda name: name if direct else None)
    client = GENERATOR._Client(
        engine="podman",
        container="postgres-test",
        env={
            "POSTGRES_USER": "operator",
            "POSTGRES_SERVER": "db.example",
            "POSTGRES_PORT": "5433",
            "POSTGRES_PASSWORD": "test-secret",
        },
    )
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="result" if kwargs.get("text") else b"dump")

    monkeypatch.setattr(GENERATOR.subprocess, "run", run)
    result = (
        client._psql("SELECT 1", database="scratch")
        if program == "psql"
        else client._dump(["--schema-only"], database="scratch")
    )
    command, options = calls[0]
    prefix = [program, "-h", "db.example", "-p", "5433"] if direct else ["podman", "exec", "postgres-test", program]
    suffix = ["-v", "ON_ERROR_STOP=1", "-tAc", "SELECT 1"] if program == "psql" else ["--schema-only"]
    assert command == [*prefix, "-U", "operator", "-d", "scratch", *suffix]
    assert options["check"]
    assert options["capture_output"]
    assert (options["env"]["PGPASSWORD"] if direct else options["env"]) == ("test-secret" if direct else None)
    assert "test-secret" not in command
    assert result == ("result" if program == "psql" else b"dump")


def _fake_client(*, exists: bool = True, definition: str = "") -> SimpleNamespace:
    calls: list[tuple[str, str, str | None]] = []

    def psql(sql: str, *, database: str | None = None) -> str:
        calls.append(("psql", sql, database))
        return definition

    def database_exists(name: str) -> bool:
        calls.append(("exists", name, None))
        return exists

    return SimpleNamespace(_psql=psql, _database_exists=database_exists, calls=calls, user="postgres")


def test_validate_target_rejects_the_configured_app_database() -> None:
    with pytest.raises(SystemExit):
        GENERATOR._validate_target("fallout_db", "fallout_db")


@pytest.mark.parametrize("name", ["postgres", "template0", "template1"])
def test_validate_target_rejects_system_databases(name: str) -> None:
    with pytest.raises(SystemExit):
        GENERATOR._validate_target(name, "fallout_db")


def test_validate_target_accepts_a_scratch_database() -> None:
    GENERATOR._validate_target("fallout_baseline_ref", "fallout_db")


def test_item_type_check_preserves_every_replayed_value() -> None:
    definition = (
        "CHECK (((item_type)::text = ANY ((ARRAY['misc'::character varying, "
        "'future_type'::character varying])::text[])))"
    )
    client = _fake_client(definition=definition)
    assert GENERATOR._item_type_check(client, "scratch") == (
        "    CONSTRAINT ck_item_item_type CHECK (item_type IN ('misc', 'future_type'))"
    )


def test_clean_dump_uses_the_replayed_constraint() -> None:
    check = "    CONSTRAINT ck_item_item_type CHECK (item_type IN ('misc', 'future_type'))"
    lines = [
        "CREATE TABLE public.alembic_version (",
        "    version_num varchar(32)",
        ");",
        "SET statement_timeout = 0;",
        "CREATE TABLE public.item (",
        "    CONSTRAINT ck_item_item_type CHECK (item_type IN ('misc'))",
        ");",
    ]
    assert GENERATOR._clean_dump(lines, check) == [
        "CREATE TABLE public.item (",
        check,
        ");",
    ]


def test_clean_dump_keeps_the_dumped_constraint_without_a_derived_check() -> None:
    line = "    CONSTRAINT ck_item_item_type CHECK (item_type IN ('misc'))"
    assert GENERATOR._clean_dump([line], None) == [line]


def test_prepare_target_reuses_an_existing_database() -> None:
    client = _fake_client(exists=True)
    GENERATOR._prepare_target(client, "scratch", skip_migrations=True, migration_env={})
    assert client.calls == [("exists", "scratch", None)]


def test_prepare_target_rejects_a_missing_reused_database() -> None:
    client = _fake_client(exists=False)
    with pytest.raises(SystemExit):
        GENERATOR._prepare_target(client, "scratch", skip_migrations=True, migration_env={})


def test_prepare_target_creates_and_migrates(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _fake_client()
    runs: list[dict] = []
    monkeypatch.setattr(GENERATOR, "_run", lambda *args, **kwargs: runs.append(kwargs))
    GENERATOR._prepare_target(client, "scratch", skip_migrations=False, migration_env={"X": "1"})
    assert [call[1] for call in client.calls] == [
        'DROP DATABASE IF EXISTS "scratch" WITH (FORCE)',
        'CREATE DATABASE "scratch" OWNER "postgres"',
    ]
    assert [call[2] for call in client.calls] == ["postgres", "postgres"]
    assert runs == [{"cwd": GENERATOR.BACKEND, "env": {"X": "1"}}]


def test_snapshot_restore_reverts_every_artifact(tmp_path: Path) -> None:
    first = tmp_path / "a.sql"
    first.write_text("old")
    second = tmp_path / "b.json"
    second.write_text("old")
    third = tmp_path / "new.py"
    snapshot = GENERATOR._snapshot({first, second, third})
    first.write_text("new")
    second.unlink()
    third.write_text("new")
    GENERATOR._restore(snapshot)
    assert first.read_text() == "old"
    assert second.read_text() == "old"
    assert not third.exists()


def test_publish_writes_the_revision_before_freezing(tmp_path: Path) -> None:
    target_sql = tmp_path / "baseline_new.sql"
    target_manifest = tmp_path / "baseline_new.json"
    revision_path = tmp_path / "old_revision.py"
    revision_path.write_text("old revision")
    target_revision = tmp_path / "new_revision.py"
    tools = tmp_path / "tools.py"
    tools.write_text("old tools")
    test_path = tmp_path / "test.py"
    test_path.write_text("old test")
    seen: dict[str, object] = {}

    def freeze() -> str:
        seen["revision_exists"] = target_revision.exists()
        seen["revision_text"] = target_revision.read_text()
        return '{"ok": true}'

    GENERATOR._publish(
        target_sql=target_sql,
        target_manifest=target_manifest,
        target_revision=target_revision,
        revision_path=revision_path,
        old_head="aaaa",
        head="bbbb",
        sql="new sql",
        revision_text="new revision",
        tools_text="new tools",
        test_text="new test",
        freeze=freeze,
        tools_path=tools,
        test_path=test_path,
        versions_dir=tmp_path,
    )
    assert seen == {"revision_exists": True, "revision_text": "new revision"}
    assert target_sql.read_text() == "new sql"
    assert target_manifest.read_text() == '{"ok": true}'
    assert not revision_path.exists()
    assert tools.read_text() == "new tools"
    assert test_path.read_text() == "new test"


def test_publish_restores_every_artifact_when_freezing_fails(tmp_path: Path) -> None:
    target_sql = tmp_path / "baseline_same.sql"
    target_sql.write_text("old sql")
    target_manifest = tmp_path / "baseline_same.json"
    target_manifest.write_text("old manifest")
    revision_path = tmp_path / "revision.py"
    revision_path.write_text("old revision")
    tools = tmp_path / "tools.py"
    tools.write_text("old tools")
    test_path = tmp_path / "test.py"
    test_path.write_text("old test")

    def freeze() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        GENERATOR._publish(
            target_sql=target_sql,
            target_manifest=target_manifest,
            target_revision=revision_path,
            revision_path=revision_path,
            old_head="same",
            head="same",
            sql="new sql",
            revision_text="new revision",
            tools_text="new tools",
            test_text="new test",
            freeze=freeze,
            tools_path=tools,
            test_path=test_path,
            versions_dir=tmp_path,
        )
    assert target_sql.read_text() == "old sql"
    assert target_manifest.read_text() == "old manifest"
    assert revision_path.read_text() == "old revision"
    assert tools.read_text() == "old tools"
    assert test_path.read_text() == "old test"


def test_publish_removes_new_artifacts_when_freezing_fails(tmp_path: Path) -> None:
    revision_path = tmp_path / "old_revision.py"
    revision_path.write_text("old revision")
    target_revision = tmp_path / "new_revision.py"
    target_sql = tmp_path / "baseline_new.sql"
    target_manifest = tmp_path / "baseline_new.json"

    def freeze() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        GENERATOR._publish(
            target_sql=target_sql,
            target_manifest=target_manifest,
            target_revision=target_revision,
            revision_path=revision_path,
            old_head="aaaa",
            head="bbbb",
            sql="new sql",
            revision_text="new revision",
            tools_text="new tools",
            test_text="new test",
            freeze=freeze,
            tools_path=tmp_path / "tools.py",
            test_path=tmp_path / "test.py",
            versions_dir=tmp_path,
        )
    assert not target_revision.exists()
    assert not target_sql.exists()
    assert not target_manifest.exists()
    assert revision_path.read_text() == "old revision"


def test_publish_restores_after_manifest_and_tools_were_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_sql = tmp_path / "baseline_same.sql"
    target_sql.write_text("old sql")
    target_manifest = tmp_path / "baseline_same.json"
    target_manifest.write_text("old manifest")
    revision_path = tmp_path / "revision.py"
    revision_path.write_text("old revision")
    tools = tmp_path / "tools.py"
    tools.write_text("old tools")
    test_path = tmp_path / "test.py"
    test_path.write_text("old test")
    original = Path.write_text

    def fail_on_test(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        if self == test_path:
            raise RuntimeError("test write failed")
        return original(self, data, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "write_text", fail_on_test)

    with pytest.raises(RuntimeError, match="test write failed"):
        GENERATOR._publish(
            target_sql=target_sql,
            target_manifest=target_manifest,
            target_revision=revision_path,
            revision_path=revision_path,
            old_head="same",
            head="same",
            sql="new sql",
            revision_text="new revision",
            tools_text="new tools",
            test_text="new test",
            freeze=lambda: '{"ok": true}',
            tools_path=tools,
            test_path=test_path,
            versions_dir=tmp_path,
        )
    assert target_sql.read_text() == "old sql"
    assert target_manifest.read_text() == "old manifest"
    assert revision_path.read_text() == "old revision"
    assert tools.read_text() == "old tools"
    assert test_path.read_text() == "old test"
