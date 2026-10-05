"""Architecture guard: routers stay thin (AGENTS.md rule 4, rule 11).

An endpoint parses params, calls a service, and maps exceptions. Queries live in
CRUD and business logic in services; the dependency direction is endpoints ->
services -> CRUD, never endpoints -> CRUD directly.

Two checks:

* **Raw loads/queries in an endpoint** — zero tolerance, no baseline. Queries
  belong in CRUD. (This is what Wave 2 cleaned up; the check locks it in.)
* **CRUD imports in an endpoint** — ratcheted. The pre-existing sites are
  recorded as ``(file, module)`` pairs so an existing router gaining another CRUD
  dependency fails, not just a brand-new router importing one.

Shared authorization lives in ``app.api.deps``, outside the scanned directory, so
the sanctioned access helpers are unaffected by this guard.
"""

import ast
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
ENDPOINTS_DIR = APP_DIR / "api" / "v1" / "endpoints"

#: Pre-existing endpoint -> CRUD imports, as ``(file name, module)``. Shrink only.
ENDPOINT_CRUD_BASELINE = frozenset(
    {
        ("dweller.py", "app.crud"),
        ("exploration.py", "app.crud"),
        ("game_control.py", "app.crud"),
        ("junk.py", "app.crud"),
        ("objective.py", "app.crud"),
        ("pregnancy.py", "app.crud"),
        ("quest.py", "app.crud"),
        ("room.py", "app.crud"),
        ("storage.py", "app.crud"),
        ("vault.py", "app.crud"),
        ("notifications.py", "app.crud.notification"),
        ("relationship.py", "app.crud.relationship"),
        ("websocket.py", "app.crud.user"),
        ("outfit.py", "app.crud"),
        ("outfit.py", "app.crud.item_base"),
        ("training.py", "app.crud"),
        ("training.py", "app.crud.dweller"),
        ("user.py", "app.crud"),
        ("user.py", "app.crud.user_profile"),
        ("weapon.py", "app.crud"),
        ("weapon.py", "app.crud.item_base"),
    }
)

SESSION_RECEIVERS = frozenset({"db_session", "session", "async_session"})
QUERY_ATTRIBUTES = frozenset({"execute"})
SESSION_ONLY_ATTRIBUTES = frozenset({"get", "refresh"})


def _crud_imports(source: str) -> set[str]:
    """Return every ``app.crud*`` module imported by a module (including nested imports)."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app.crud"):
                modules.add(node.module)
            elif node.module == "app" and any(alias.name == "crud" for alias in node.names):
                modules.add("app.crud")
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name.startswith("app.crud"))
    return modules


def _raw_query_lines(source: str) -> list[tuple[int, str]]:
    """Return (line, description) for raw session loads and query building in a module."""
    violations: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "select":
            violations.append((node.lineno, "select()"))
        elif isinstance(func, ast.Attribute):
            receiver = func.value.id if isinstance(func.value, ast.Name) else None
            if func.attr in QUERY_ATTRIBUTES:
                violations.append((node.lineno, f".{func.attr}()"))
            elif func.attr in SESSION_ONLY_ATTRIBUTES and receiver in SESSION_RECEIVERS:
                violations.append((node.lineno, f"session.{func.attr}()"))
    return sorted(violations)


def _endpoint_files() -> list[tuple[Path, str]]:
    return [(path, path.name) for path in sorted(ENDPOINTS_DIR.glob("*.py"))]


def test_endpoints_do_not_query_directly() -> None:
    """Queries live in CRUD; endpoints orchestrate through services. No baseline."""
    offenders = []
    for path, name in _endpoint_files():
        for line, description in _raw_query_lines(path.read_text(encoding="utf-8")):
            offenders.append(f"{name}:{line} {description}")
    assert not offenders, "Endpoints must not issue queries or load rows directly:\n" + "\n".join(offenders)


def test_endpoints_do_not_import_crud() -> None:
    """New endpoint -> CRUD dependencies fail; the baseline must shrink, never grow."""
    found = set()
    for path, name in _endpoint_files():
        found.update((name, module) for module in _crud_imports(path.read_text(encoding="utf-8")))

    new_violations = found - ENDPOINT_CRUD_BASELINE
    stale_entries = ENDPOINT_CRUD_BASELINE - found

    messages = [
        f"{name} imports {module} (endpoints call services, not CRUD)" for name, module in sorted(new_violations)
    ]
    messages += [f"baseline entry {name} / {module} is stale; remove it" for name, module in sorted(stale_entries)]
    assert not messages, "Endpoint dependencies changed:\n" + "\n".join(messages)


def test_guard_detects_crud_imports() -> None:
    """Self-test: package-attribute, submodule, and plain imports are all caught."""
    source = (
        "from app import crud\n"
        "from app.crud.notification import notification\n"
        "from app.crud import room\n"
        "import app.crud.item_base\n"
        "from app.services.vault_service import vault_service\n"
    )
    assert _crud_imports(source) == {"app.crud", "app.crud.notification", "app.crud.item_base"}


def test_guard_detects_raw_queries() -> None:
    """Self-test: select(), execute(), and session loads are flagged; plain attribute calls are not."""
    source = (
        "x = select(Room).where(Room.id == 1)\n"
        "y = await db_session.execute(query)\n"
        "z = await db_session.get(Room, 1)\n"
        "w = await db_session.refresh(obj)\n"
        "v = await redis_client.get('k')\n"
        "u = payload.get('k')\n"
    )
    assert [description for _, description in _raw_query_lines(source)] == [
        "select()",
        ".execute()",
        "session.get()",
        "session.refresh()",
    ]


def test_guard_leaves_other_attribute_calls_alone() -> None:
    """Self-test: a non-session receiver's .get()/refresh() is not a session load."""
    source = "a = cache.get('k')\nb = obj.refresh()\nc = settings.get('x')\n"
    assert _raw_query_lines(source) == []
