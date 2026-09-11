"""Architecture guards for the service-layer contract (docs/backend/SERVICE_LAYER.md).

Services and CRUD stay transport-free: they may not import or raise ``HTTPException``.
``app/utils/exceptions.py`` stays free of fastapi imports.

Dependency direction is one-way: CRUD modules may only use the shared policy kernel
``app.services.room_assignment_policy``; messaging lives in ``app.core.event_bus``,
outside the service layer entirely. Every other CRUD -> service dependency is
recorded in ``CRUD_SERVICE_BASELINE`` and must shrink as domain batches migrate; new entries fail the suite. The same ratchet
applies to raw ``select()``/``exec()`` queries in ``app/services`` (``SERVICES_SELECT_BASELINE``)
and to non-conforming top-level service module names (``SERVICE_NAME_GRANDFATHER``).
A baseline entry with no remaining violations also fails, so the lists stay honest.
"""

import ast
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
GUARDED_DIRS = ("services", "crud")
EXCEPTIONS_FILE = APP_DIR / "utils" / "exceptions.py"

CRUD_SERVICE_ALLOWLIST = frozenset({"app.services.room_assignment_policy"})
CRUD_SERVICE_BASELINE = frozenset({})
SERVICES_SELECT_BASELINE = frozenset()
SERVICE_NAME_PATTERN = re.compile(r"^([a-z][a-z0-9_]*_service|__init__)\.py$")
SERVICE_NAME_GRANDFATHER = frozenset(
    {
        "ai_constants.py",
        "dweller_ai.py",
        "game_loop.py",
        "health_check.py",
        "objective_evaluators.py",
        "objective_notifications.py",
        "resource_manager.py",
        "room_assignment_policy.py",
        "stream_manager.py",
        "tick_chain.py",
        "vault_seed.py",
        "websocket_manager.py",
    }
)


def _http_exception_violations(source: str) -> list[tuple[int, str]]:
    """Return (line, description) for every HTTPException reference in a module."""
    tree = ast.parse(source)
    violations: list[tuple[int, str]] = []
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(alias.name == "HTTPException" for alias in node.names):
            violations.append((node.lineno, "import of HTTPException"))
            aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "HTTPException")
        elif isinstance(node, ast.Import):
            aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "HTTPException")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and (node.id == "HTTPException" or node.id in aliases):
            violations.append((node.lineno, "reference to HTTPException"))
        elif isinstance(node, ast.Attribute) and node.attr == "HTTPException":
            violations.append((node.lineno, "attribute reference to HTTPException"))
    return violations


def _fastapi_import_lines(source: str) -> list[int]:
    """Return line numbers of fastapi imports in a module."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(name.startswith("fastapi") for name in names):
                lines.append(node.lineno)
    return lines


def test_services_and_crud_do_not_reference_http_exception() -> None:
    """No transport exceptions below the API layer."""
    violations = []
    for dirname in GUARDED_DIRS:
        for path in sorted((APP_DIR / dirname).rglob("*.py")):
            for line, description in _http_exception_violations(path.read_text(encoding="utf-8")):
                violations.append(f"{path.relative_to(APP_DIR)}:{line} {description}")
    assert not violations, "Transport exceptions leaked below the API layer:\n" + "\n".join(violations)


def test_exceptions_module_has_no_fastapi_imports() -> None:
    """Domain exceptions are transport-free: fastapi must not be imported."""
    lines = _fastapi_import_lines(EXCEPTIONS_FILE.read_text(encoding="utf-8"))
    assert not lines, f"app/utils/exceptions.py imports fastapi at lines: {lines}"


def _service_imports(source: str) -> set[str]:
    """Return app.services modules imported anywhere in a module (including nested imports).

    Level-two relative imports (``from ..services import X``) resolve against the
    ``app`` package from inside ``app.crud``/``app.services``, so normalize them
    to the corresponding ``app.services`` path instead of missing them.
    """
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app.services"):
                modules.add(node.module)
            elif (
                node.level
                and node.level >= 2
                and node.module
                and (node.module == "services" or node.module.startswith("services."))
            ):
                modules.add(f"app.{node.module}")
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name.startswith("app.services"))
    return modules


def _select_call_lines(source: str) -> list[int]:
    """Return sorted unique line numbers of raw select(), exec(), text(), and execute() calls in a module."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id in ("select", "text")) or (
                isinstance(func, ast.Attribute) and func.attr in ("select", "exec", "execute")
            ):
                lines.append(node.lineno)
    return sorted(set(lines))


def test_crud_does_not_depend_on_services() -> None:
    """CRUD depends on services only via shared kernels; the baseline must shrink, never grow."""
    found = set()
    for path in sorted((APP_DIR / "crud").rglob("*.py")):
        for module in _service_imports(path.read_text(encoding="utf-8")):
            if module not in CRUD_SERVICE_ALLOWLIST:
                found.add((path.name, module))
    new_violations = found - CRUD_SERVICE_BASELINE
    stale_entries = CRUD_SERVICE_BASELINE - found
    messages = [f"{name} imports {module} (new CRUD -> service dependency)" for name, module in sorted(new_violations)]
    messages += [f"baseline entry {name} / {module} is stale; remove it" for name, module in sorted(stale_entries)]
    assert not messages, "CRUD -> service dependencies changed:\n" + "\n".join(messages)


def test_services_do_not_query_directly() -> None:
    """Raw select() stays in CRUD; services orchestrate. The baseline must shrink, never grow."""
    found = set()
    for path in sorted((APP_DIR / "services").rglob("*.py")):
        if _select_call_lines(path.read_text(encoding="utf-8")):
            found.add(path.relative_to(APP_DIR / "services").as_posix())
    new_files = found - SERVICES_SELECT_BASELINE
    stale_entries = SERVICES_SELECT_BASELINE - found
    messages = [f"{name} issues raw select()/exec() (new SQL in service layer)" for name in sorted(new_files)]
    messages += [f"baseline entry {name} is stale; remove it" for name in sorted(stale_entries)]
    assert not messages, "Raw select()/exec() usage in services changed:\n" + "\n".join(messages)


def test_service_module_names_follow_convention() -> None:
    """New top-level service modules are *_service.py; the grandfather list never grows."""
    found = {path.name for path in (APP_DIR / "services").glob("*.py") if not SERVICE_NAME_PATTERN.match(path.name)}
    new_names = found - SERVICE_NAME_GRANDFATHER
    stale_entries = SERVICE_NAME_GRANDFATHER - found
    messages = [f"{name} breaks the *_service.py naming convention" for name in sorted(new_names)]
    messages += [f"grandfather entry {name} is stale; remove it" for name in sorted(stale_entries)]
    assert not messages, "Service module names changed:\n" + "\n".join(messages)


def test_crud_stays_flat_and_lowercase() -> None:
    """CRUD modules stay flat lowercase files; no subpackages, no new naming styles."""
    problems = []
    for path in sorted((APP_DIR / "crud").rglob("*")):
        if any(part.startswith((".", "__")) for part in path.relative_to(APP_DIR / "crud").parts):
            continue
        if path.is_dir():
            problems.append(f"unexpected subpackage: {path.name}")
        elif path.suffix == ".py" and (path.name != path.name.lower() or "-" in path.stem):
            problems.append(f"non-lowercase module: {path.name}")
    assert not problems, "CRUD layout changed:\n" + "\n".join(problems)


def test_guard_detects_http_exception_violation() -> None:
    """Self-test: the violation finder catches aliased imports, names, and attribute access."""
    source = (
        "from fastapi import HTTPException as HE\n"
        "import fastapi\n"
        "def f() -> None:\n"
        "    raise HE(400)\n"
        "def g() -> None:\n"
        "    raise fastapi.HTTPException(400)\n"
    )
    violations = _http_exception_violations(source)
    assert len(violations) == 3
    assert all("HTTPException" in description for _, description in violations)


def test_guard_detects_nested_service_import() -> None:
    """Self-test: service imports are found even inside functions, with exact module names."""
    source = (
        "from app.crud.base import CRUDBase\n"
        "def f() -> None:\n"
        "    from app.services.vault_service import vault_service\n"
        "    from app.services.event_bus import event_bus\n"
    )
    assert _service_imports(source) == {"app.services.vault_service", "app.services.event_bus"}


def test_guard_detects_relative_service_import() -> None:
    """Self-test: level-two relative imports normalize to app.services paths."""
    source = (
        "from ..services import vault_service\n"
        "from ..services.room_assignment_policy import validate\n"
        "from . import storage\n"
    )
    assert _service_imports(source) == {"app.services", "app.services.room_assignment_policy"}


def test_guard_detects_select_calls() -> None:
    """Self-test: bare/attribute select(), exec(), text(), and execute() calls are reported with line numbers."""
    source = (
        "x = select(Model).where(Model.id == 1)\n"
        "y = session.execute(select(Model))\n"
        "z = session.exec(query)\n"
        "w = selected_items\n"
        "v = session.execute(text('SELECT 1'))\n"
    )
    assert _select_call_lines(source) == [1, 2, 3, 5]


def test_service_name_pattern() -> None:
    """Self-test: the naming pattern accepts services and rejects helpers."""
    assert SERVICE_NAME_PATTERN.match("vault_service.py")
    assert SERVICE_NAME_PATTERN.match("__init__.py")
    assert not SERVICE_NAME_PATTERN.match("vault_seed.py")
    assert not SERVICE_NAME_PATTERN.match("VaultService.py")
