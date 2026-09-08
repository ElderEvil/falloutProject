"""Architecture guards for the service-layer contract (docs/backend/SERVICE_LAYER.md).

Services and CRUD stay transport-free: they may not import or raise ``HTTPException``.
``app/utils/exceptions.py`` stays free of fastapi imports.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
GUARDED_DIRS = ("services", "crud")
EXCEPTIONS_FILE = APP_DIR / "utils" / "exceptions.py"


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
