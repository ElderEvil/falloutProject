"""Architecture guard: migrations must not depend on live application code.

A migration that imports ``app.*`` re-reads the application at upgrade time, so a
later refactor of that module changes what an old migration writes — or breaks
``alembic upgrade head`` outright before ``upgrade()`` even runs. The outfit
backfills already froze their catalog data for exactly this reason
(``2026_09_19_0002``); this guard makes that the rule going forward.

The existing offenders are recorded in ``MIGRATION_APP_IMPORT_BASELINE`` and must
shrink as each is frozen, never grow. A baseline entry that no longer violates
also fails, so the list stays honest.

Note: this is a forward ratchet. Wholesale rewriting of already-applied
migrations is deliberately out of scope — the frozen copy must be behaviourally
identical to the applied one or fresh databases diverge from existing ones.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = APP_DIR / "alembic" / "versions"

#: Pre-existing migrations that import live app code. Shrink only.
MIGRATION_APP_IMPORT_BASELINE = frozenset(
    {
        "2026_01_08_1455-34f9ec11db72_initial.py",
        "2026_01_26_1313-fc75e738a303_add_room_image_urls.py",
        "2026_08_14_2026-8155dd024c0b_backfill_outfit_image_urls.py",
        "2026_08_14_2027-6e74d20b1b5e_backfill_item_and_legendary_images.py",
        "2026_08_14_2028-5c88a7e4d918_backfill_legendary_dweller_thumbnails.py",
        "2026_09_12_0001-b7e4c1a9f2d3_add_world_place_registry.py",
    }
)


def _app_imports(source: str) -> set[str]:
    """Return every ``app.*`` module imported by a module (including nested imports)."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app."):
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name.startswith("app."))
    return modules


def test_migrations_do_not_import_live_app_code() -> None:
    """Migrations freeze the data they need; the baseline must shrink, never grow."""
    found = set()
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        if _app_imports(path.read_text(encoding="utf-8")):
            found.add(path.name)

    new_violations = found - MIGRATION_APP_IMPORT_BASELINE
    stale_entries = MIGRATION_APP_IMPORT_BASELINE - found

    messages = [
        f"{name} imports live app code (freeze the value it needs in the migration)" for name in sorted(new_violations)
    ]
    messages += [f"baseline entry {name} is stale; remove it" for name in sorted(stale_entries)]
    assert not messages, "Migration dependencies on live app code changed:\n" + "\n".join(messages)


def test_guard_detects_app_imports() -> None:
    """Self-test: absolute from-imports and plain imports of app.* are both caught."""
    source = (
        "from app.utils.places import collision_nudge\n"
        "from app.core.security import get_password_hash\n"
        "import app.utils.places\n"
        "from sqlalchemy import text\n"
        "import hashlib\n"
    )
    assert _app_imports(source) == {"app.utils.places", "app.core.security"}


def test_guard_ignores_non_app_imports() -> None:
    """Self-test: a migration importing only third-party/stdlib modules is clean."""
    source = "import sqlalchemy as sa\nfrom alembic import op\nfrom collections.abc import Sequence\n"
    assert _app_imports(source) == set()
