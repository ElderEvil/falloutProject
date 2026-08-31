"""Regression coverage for the prompt provenance Alembic migration."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _migration_module(filename: str):
    path = Path(__file__).parents[2] / f"alembic/versions/{filename}"
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prompt_provenance_upgrade_supports_sqlite_and_duplicate_legacy_prompts() -> None:
    """Upgrade backfills distinct versions before adding SQLite-compatible constraints."""
    engine = sa.create_engine("sqlite://")
    schema_migration = _migration_module("2026_08_31_0001-e6f7a8b9c0d1_add_prompt_versioning_and_llm_provenance.py")
    seed_migration = _migration_module("2026_08_31_0002-f7a8b9c0d1e2_seed_prompt_registry.py")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE prompt ("
                "id VARCHAR PRIMARY KEY, prompt_name VARCHAR NOT NULL, description VARCHAR NOT NULL, "
                "prompt_template VARCHAR NOT NULL, entity_id VARCHAR)"
            )
        )
        connection.execute(sa.text("CREATE TABLE llminteraction (id VARCHAR PRIMARY KEY)"))
        connection.execute(
            sa.text(
                "INSERT INTO prompt (id, prompt_name, description, prompt_template) VALUES "
                "('a', 'chat', 'first', 'one'), ('b', 'chat', 'second', 'two')"
            )
        )

        with Operations.context(MigrationContext.configure(connection)):
            schema_migration.upgrade()
        with Operations.context(MigrationContext.configure(connection)):
            seed_migration.upgrade()

        rows = connection.execute(
            sa.text("SELECT version, is_active FROM prompt WHERE prompt_name = 'chat' ORDER BY id")
        ).all()
        assert rows == [(1, 1), (2, 0)]
        prompt_names = (
            connection.execute(sa.text("SELECT prompt_name FROM prompt ORDER BY prompt_name")).scalars().all()
        )
        assert prompt_names == ["backstory", "chat", "chat", "extend_bio", "visual_attributes"]
        indexes = sa.inspect(connection).get_indexes("prompt")
        active_index = next(index for index in indexes if index["name"] == "ix_prompt_active_name")
        assert active_index["dialect_options"]["sqlite_where"] is not None
