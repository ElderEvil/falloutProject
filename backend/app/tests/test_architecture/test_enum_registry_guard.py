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

#: Pre-existing enum declarations outside the registry, as ``(path, class name)``.
#: Declaration-level, not file-level: adding another enum to a grandfathered file
#: must fail, so the baseline can only shrink. Shrink only.
ENUM_REGISTRY_BASELINE = frozenset(
    {
        ("models/crafting_order.py", "CraftingOrderStatus"),
        ("models/exploration.py", "ExplorationStatus"),
        ("models/incident.py", "IncidentType"),
        ("models/incident.py", "IncidentStatus"),
        ("models/incident.py", "IncidentFamily"),
        ("models/incident.py", "IncidentObjective"),
        ("models/notification.py", "NotificationType"),
        ("models/notification.py", "NotificationPriority"),
        ("models/quest.py", "QuestType"),
        ("models/quest_requirement.py", "RequirementType"),
        ("models/quest_reward.py", "RewardType"),
        ("models/training.py", "TrainingStatus"),
        ("schemas/exploration_event.py", "ExplorationEventType"),
        ("schemas/happiness.py", "HappinessReasonCode"),
        ("services/health_check.py", "ServiceStatus"),
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
        found.update((relative, name) for _, name in _enum_declarations(path.read_text(encoding="utf-8")))

    new_violations = found - ENUM_REGISTRY_BASELINE
    stale_entries = ENUM_REGISTRY_BASELINE - found

    messages = [
        f"{relative} declares {name} outside app/core/enums.py (move it to the registry)"
        for relative, name in sorted(new_violations)
    ]
    messages += [f"baseline entry {relative} / {name} is stale; remove it" for relative, name in sorted(stale_entries)]
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
