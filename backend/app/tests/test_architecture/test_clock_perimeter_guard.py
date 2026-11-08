"""Clock perimeter guard: naive-UTC producers live only in ``app.utils.time``.

The storage contract is naive UTC (README timestamp convention). ``datetime.utcnow`` is
deprecated and a bare ``datetime.now()`` reads local time, so both are banned. Stripping
``tzinfo`` is only correct in the clock module, where interpreting naive values as UTC is
the documented contract; elsewhere an offset must be converted first with ``as_utc`` or
``as_naive_utc``.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
EXCLUDED_DIRS = frozenset({"tests", "alembic"})
CLOCK_MODULE = "time.py"


def _guarded_files() -> list[Path]:
    return [path for path in APP_DIR.rglob("*.py") if not EXCLUDED_DIRS.intersection(path.parts)]


def _datetime_call(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "datetime":
        return func.attr
    return None


def _strips_tzinfo(node: ast.Call) -> bool:
    if not (isinstance(node.func, ast.Attribute) and node.func.attr == "replace"):
        return False
    return any(
        keyword.arg == "tzinfo" and isinstance(keyword.value, ast.Constant) and keyword.value.value is None
        for keyword in node.keywords
    )


def test_clock_producers_are_centralized() -> None:
    violations: list[str] = []
    for path in _guarded_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call = _datetime_call(node)
            if call == "utcnow":
                violations.append(f"{path}:{node.lineno}: datetime.utcnow")
            if call == "now" and not node.args and not any(keyword.arg == "tz" for keyword in node.keywords):
                violations.append(f"{path}:{node.lineno}: bare datetime.now()")
            if _strips_tzinfo(node) and path.name != CLOCK_MODULE:
                violations.append(f"{path}:{node.lineno}: .replace(tzinfo=None)")

    assert not violations, "Clock producers must go through app.utils.time.utcnow/as_utc:\n" + "\n".join(violations)
