"""Architecture guard: Python enums have one owner and one dependency direction.

Enums are defined in ``app/core/enums.py``; model modules must not define their own
``StrEnum``/``IntEnum`` and ``app/core`` must not import ``app.models`` (the old
direction created a cycle that only deferred imports hid).
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = APP_DIR / "models"
CORE_DIR = APP_DIR / "core"
ENUM_BASES = frozenset({"StrEnum", "IntEnum"})


def enum_class_names(source: str) -> set[str]:
    """Top-level classes in ``source`` that subclass ``StrEnum`` or ``IntEnum``."""
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and any(ast.unparse(base).split(".")[-1] in ENUM_BASES for base in node.bases)
    }


def core_model_imports(source: str) -> set[str]:
    """Every ``app.models`` import in a core module, with its line number."""
    tree = ast.parse(source)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and (node.module == "app.models" or node.module.startswith("app.models."))
        ):
            violations.add(f"{node.module} (line {node.lineno})")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "app.models" or alias.name.startswith("app.models."):
                    violations.add(f"{alias.name} (line {node.lineno})")
    return violations


def test_model_modules_do_not_define_python_enums() -> None:
    violations = {
        str(path.relative_to(APP_DIR)): sorted(names)
        for path in MODELS_DIR.rglob("*.py")
        if (names := enum_class_names(path.read_text(encoding="utf-8")))
    }

    assert not violations, (
        "Model modules define StrEnum/IntEnum classes; move them to app/core/enums.py:\n  "
        + "\n  ".join(f"{path}: {names}" for path, names in sorted(violations.items()))
    )


def test_core_modules_do_not_import_models() -> None:
    violations = {
        str(path.relative_to(APP_DIR)): sorted(imports)
        for path in CORE_DIR.rglob("*.py")
        if (imports := core_model_imports(path.read_text(encoding="utf-8")))
    }

    assert not violations, (
        "app/core must not import app.models; move the shared contract into app/core:\n  "
        + "\n  ".join(f"{path}: {imports}" for path, imports in sorted(violations.items()))
    )


def test_moved_enums_are_defined_in_core() -> None:
    from app.core import enums

    moved = (
        enums.CraftingOrderStatus,
        enums.ExplorationStatus,
        enums.IncidentFamily,
        enums.IncidentObjective,
        enums.IncidentStatus,
        enums.IncidentType,
        enums.NotificationPriority,
        enums.NotificationType,
        enums.QuestType,
        enums.RequirementType,
        enums.RewardType,
        enums.TrainingStatus,
    )

    assert {enum_cls.__module__ for enum_cls in moved} == {"app.core.enums"}


def test_detectors_catch_the_old_shapes() -> None:
    assert enum_class_names("from enum import StrEnum\nclass Bad(StrEnum):\n    A = 'a'\n") == {"Bad"}
    assert enum_class_names("from enum import IntEnum\nclass Bad(IntEnum):\n    A = 1\n") == {"Bad"}
    assert enum_class_names("class Fine(SQLModel):\n    pass\n") == set()
    assert core_model_imports("from app.models.vault import Vault\n") == {"app.models.vault (line 1)"}
