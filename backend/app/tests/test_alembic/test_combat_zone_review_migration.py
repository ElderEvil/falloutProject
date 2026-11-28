"""The Combat Zone review migration must not collide with the frozen legacy graph."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.tests.test_alembic._support import BASELINE_VERSIONS, load_migration, migration_path

BACKEND = Path(__file__).resolve().parents[3]
REVISION = "b9d4e2f7a1c6"
PARENT = "d1e4b8c2a9f5"
MIGRATION = load_migration(REVISION, "combat_zone_review_fixes", BASELINE_VERSIONS)


def test_revision_is_unique_across_baseline_and_legacy_graphs() -> None:
    assert MIGRATION.revision == REVISION
    assert MIGRATION.down_revision == PARENT
    legacy = ScriptDirectory.from_config(Config(str(BACKEND / "alembic-legacy.ini")))
    current = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert REVISION not in {revision.revision for revision in legacy.walk_revisions()}
    assert REVISION in {revision.revision for revision in current.walk_revisions()}
