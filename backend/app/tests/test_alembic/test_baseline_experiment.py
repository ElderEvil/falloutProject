"""Exercise the opt-in squash against PostgreSQL, using scratch databases only."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine
from typer.testing import CliRunner

from app.alembic import baseline_tools
from app.core.config import settings
from app.core.security import verify_password
from app.tests.test_alembic import test_data_migrations as legacy
from app.tests.test_alembic.test_data_migrations import MigrationHarness

pytestmark = pytest.mark.integration
harness = legacy.harness

BACKEND = Path(__file__).resolve().parents[3]
BASELINE = "squash_b7e3d9c1a5f2"
LEGACY_HEAD = "b7e3d9c1a5f2"
SEED_EXCLUSIONS = {
    "objective": ("id",),
    "prompt": (),
    "user": ("id", "created_at", "updated_at", "hashed_password"),
    "vault": ("id", "created_at", "updated_at", "user_id"),
    "vaultslot": ("id", "created_at", "updated_at", "vault_id"),
}


def _config() -> Config:
    return Config(str(BACKEND / "alembic-squash.ini"))


def schema_state(db: MigrationHarness) -> dict:
    async def read() -> dict:
        engine = create_async_engine(db.url)
        try:
            async with engine.connect() as connection:
                return await connection.run_sync(baseline_tools.schema_state)
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _rows(db: MigrationHarness, table: str, *, exclude: tuple[str, ...] = ()) -> list[str]:
    assert table.isidentifier()
    rows = db.fetch(f'SELECT to_jsonb(t) FROM public."{table}" t')  # ruff: ignore[hardcoded-sql-expression] — identifier validated above; table names come from pg_tables or constants
    return sorted(json.dumps({k: v for k, v in row.items() if k not in exclude}, sort_keys=True) for (row,) in rows)


def test_baseline_matches_full_history_and_bootstrap(harness: MigrationHarness) -> None:
    harness.upgrade(LEGACY_HEAD)
    expected_schema = schema_state(harness)
    seeds = {table: _rows(harness, table, exclude=excluded) for table, excluded in SEED_EXCLUSIONS.items()}
    # The imported harness creates its own UUID-named database and cleans it up.
    harness.execute("DROP SCHEMA public CASCADE")
    harness.execute("CREATE SCHEMA public")
    command.upgrade(_config(), "head")
    actual_schema = schema_state(harness)
    assert actual_schema == expected_schema
    for table, expected in seeds.items():
        assert _rows(harness, table, exclude=SEED_EXCLUSIONS[table]) == expected, table
    assert harness.scalar("SELECT version_num FROM alembic_version") == BASELINE
    for email, password in (
        (settings.FIRST_SUPERUSER_EMAIL, settings.FIRST_SUPERUSER_PASSWORD),
        (settings.EMAIL_TEST_USER, "testpassword"),
    ):
        hashed = harness.scalar('SELECT hashed_password FROM public."user" WHERE email = :email', email=email)
        assert verify_password(password, hashed)


def test_stamping_completed_history_preserves_all_rows_and_schema(harness: MigrationHarness) -> None:
    harness.upgrade(LEGACY_HEAD)
    tables = harness.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'alembic_version' "
        "ORDER BY tablename"
    )
    expected_schema = schema_state(harness)
    expected_rows = {table: _rows(harness, table) for (table,) in tables}
    command.stamp(_config(), "head", purge=True)
    command.upgrade(_config(), "head")
    assert harness.scalar("SELECT version_num FROM alembic_version") == BASELINE
    assert schema_state(harness) == expected_schema
    assert {table: _rows(harness, table) for (table,) in tables} == expected_rows


def test_followup_revision_upgrades_and_downgrades(harness: MigrationHarness, tmp_path: Path) -> None:
    versions = tmp_path / "versions"
    shutil.copytree(BACKEND / "app/alembic/baseline_versions", versions)
    (versions / "followup.py").write_text(
        "from alembic import op\nimport sqlalchemy as sa\n"
        'revision = "squash_followup"\n'
        f'down_revision = "{BASELINE}"\n'
        'def upgrade():\n    op.create_table("squash_probe", sa.Column("id", sa.Integer(), primary_key=True))\n'
        'def downgrade():\n    op.drop_table("squash_probe")\n'
    )
    config = _config()
    config.set_main_option("version_locations", str(versions))
    command.upgrade(config, "head")
    assert harness.scalar("SELECT to_regclass('public.squash_probe')::text") == "squash_probe"
    command.downgrade(config, BASELINE)
    assert harness.scalar("SELECT to_regclass('public.squash_probe')::text") is None
    assert harness.scalar("SELECT version_num FROM alembic_version") == BASELINE
    with pytest.raises(RuntimeError, match="baseline cannot be downgraded"):
        command.downgrade(config, "base")
    assert harness.scalar("SELECT count(*) FROM objective") > 0


def test_guarded_adoption_preserves_rows_and_is_idempotent(harness: MigrationHarness) -> None:
    harness.upgrade(LEGACY_HEAD)
    expected = _rows(harness, "objective")
    database = baseline_tools.make_url(harness.url).database
    check = CliRunner().invoke(baseline_tools.app, ["adopt", "--database", database])
    assert check.exit_code == 0
    assert json.loads(check.output)["schema_matches"]
    assert harness.scalar("SELECT version_num FROM alembic_version") == LEGACY_HEAD
    for _ in range(2):
        result = asyncio.run(baseline_tools.inspect_database(database, apply=True))
        assert result["applied"]
        assert harness.scalar("SELECT version_num FROM alembic_version") == BASELINE
        assert _rows(harness, "objective") == expected


@pytest.mark.parametrize("failure", ["schema", "revision"])
def test_guard_refuses_drift_without_stamping(harness: MigrationHarness, failure: str) -> None:
    harness.upgrade(LEGACY_HEAD)
    if failure == "schema":
        harness.execute("ALTER TABLE exploration ALTER COLUMN unclaimed_loot DROP NOT NULL")
        expected_revision = LEGACY_HEAD
        message = "Schema drift"
    else:
        harness.execute("UPDATE alembic_version SET version_num = 'unsupported_revision'")
        expected_revision = "unsupported_revision"
        message = "frozen legacy head"
    database = baseline_tools.make_url(harness.url).database
    with pytest.raises(RuntimeError, match=message):
        asyncio.run(baseline_tools.inspect_database(database, apply=True))
    assert harness.scalar("SELECT version_num FROM alembic_version") == expected_revision


def test_cli_requires_matching_database_without_exposing_credentials() -> None:
    result = CliRunner().invoke(baseline_tools.app, ["adopt", "--database", "wrong_database", "--apply"])
    assert result.exit_code == 1
    assert "does not match --database" in result.output
    assert settings.POSTGRES_PASSWORD not in result.output


def test_freeze_records_reference_without_overwriting(harness: MigrationHarness, tmp_path: Path) -> None:
    harness.upgrade(LEGACY_HEAD)
    database = baseline_tools.make_url(harness.url).database
    output = tmp_path / "reference.json"
    arguments = ["freeze", "--database", database, "--output", str(output)]
    runner = CliRunner()
    assert runner.invoke(baseline_tools.app, arguments).exit_code == 0
    frozen = json.loads(output.read_text())
    assert frozen["legacy_revision"] == LEGACY_HEAD
    assert frozen["baseline_revision"] == BASELINE
    assert frozen["schema"] == schema_state(harness)
    assert runner.invoke(baseline_tools.app, arguments).exit_code == 1
    assert json.loads(output.read_text()) == frozen
    assert harness.scalar("SELECT version_num FROM alembic_version") == LEGACY_HEAD
