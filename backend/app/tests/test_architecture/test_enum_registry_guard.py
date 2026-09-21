"""Architecture guard: enums are declared once, in ``app/core/enums.py``.

AGENTS.md rule 4 puts enums with the other cross-cutting infrastructure in
``app/core/``. Declaring them beside the models, schemas, or services that happen
to use them first leaves two sources of truth and makes a PostgreSQL enum change
easy to miss — the value lives with a feature while the column lives in a
migration.

Everything under ``app/core`` is allowed (that is the sanctioned home), as are
tests and migrations. The pre-existing offenders are recorded in
``ENUM_REGISTRY_BASELINE`` and must shrink as each domain moves, never grow; a
baseline entry that no longer violates also fails, so the list stays honest.

Relocating an enum must not change its stored labels: a pure move needs no
``ALTER TYPE``, and ``PG_ENUM_LABELS_SNAPSHOT`` only changes when a value does.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
CORE_DIR_NAME = "core"
SKIP_DIRS = frozenset({"tests", "alembic", "__pycache__"})

#: Bases that mark a class as an enum declaration.
ENUM_BASES = frozenset({"StrEnum", "IntEnum", "Enum", "Flag", "IntFlag", "CaseInsensitiveEnum"})

#: Pre-existing files that declare enums outside the registry. Shrink only.
ENUM_REGISTRY_BASELINE = frozenset(
    {
        "models/crafting_order.py",
        "models/exploration.py",
        "models/incident.py",
        "models/notification.py",
        "models/quest.py",
        "models/quest_requirement.py",
        "models/quest_reward.py",
        "models/training.py",
        "schemas/exploration_event.py",
        "schemas/happiness.py",
        "services/health_check.py",
    }
)


def _enum_declarations(source: str) -> list[tuple[int, str]]:
    """Return (line, class name) for every module-level class that subclasses an enum base."""
    declarations: list[tuple[int, str]] = []
    for node in ast.parse(source).body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {base.id for base in node.bases if isinstance(base, ast.Name)}
        bases |= {base.attr for base in node.bases if isinstance(base, ast.Attribute)}
        if bases & ENUM_BASES:
            declarations.append((node.lineno, node.name))
    return declarations


def _guarded_files() -> list[tuple[Path, str]]:
    """Every application module outside ``app/core``, tests, and migrations."""
    guarded: list[tuple[Path, str]] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        relative = path.relative_to(APP_DIR)
        if relative.parts[0] in SKIP_DIRS or relative.parts[0] == CORE_DIR_NAME:
            continue
        guarded.append((path, relative.as_posix()))
    return guarded


def test_enums_are_declared_in_the_registry() -> None:
    """New enums belong in app/core/enums.py; the baseline must shrink, never grow."""
    found = set()
    for path, relative in _guarded_files():
        if _enum_declarations(path.read_text(encoding="utf-8")):
            found.add(relative)

    new_violations = found - ENUM_REGISTRY_BASELINE
    stale_entries = ENUM_REGISTRY_BASELINE - found

    messages = [
        f"{relative} declares an enum outside app/core/enums.py (move it to the registry)"
        for relative in sorted(new_violations)
    ]
    messages += [f"baseline entry {relative} is stale; remove it" for relative in sorted(stale_entries)]
    assert not messages, "Enum locations changed:\n" + "\n".join(messages)


def test_guard_detects_enum_declarations() -> None:
    """Self-test: direct and project-base subclasses are caught, plain classes are not."""
    source = (
        "from enum import StrEnum\n"
        "class Known(StrEnum):\n"
        "    A = 'a'\n"
        "class Inherited(CaseInsensitiveEnum):\n"
        "    B = 'b'\n"
        "class ViaAttribute(enum.IntEnum):\n"
        "    C = 1\n"
        "class NotAnEnum:\n"
        "    pass\n"
    )
    assert [name for _, name in _enum_declarations(source)] == ["Known", "Inherited", "ViaAttribute"]


def test_guard_ignores_imports_and_reexports() -> None:
    """Self-test: importing or re-exporting an enum is not declaring one."""
    source = "from app.core.enums import WeaponTypeEnum\nWeaponTypeEnum = WeaponTypeEnum\n"
    assert _enum_declarations(source) == []
