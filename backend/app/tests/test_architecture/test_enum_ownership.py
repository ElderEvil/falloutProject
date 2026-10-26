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


def _module_name(path: Path) -> str:
    """Import-style module name for a file under ``app/`` (``app.core.foo``)."""
    return ".".join(path.relative_to(APP_DIR.parent).with_suffix("").parts)


def _is_models_module(module: str) -> bool:
    """Whether a resolved module name points at ``app.models`` or a submodule."""
    return module == "app.models" or module.startswith("app.models.")


def _relative_base(module_name: str, level: int) -> list[str]:
    """Package parts a relative import resolves from; empty for an invalid level."""
    package_parts = module_name.split(".")[:-1]
    up = level - 1
    if up > len(package_parts):
        return []
    return package_parts[: len(package_parts) - up]


def core_model_imports(source: str, module_name: str) -> set[str]:
    """Every ``app.models`` import in a core module, with its line number.

    Handles absolute imports, relative imports resolved against ``module_name``,
    and package-level forms such as ``from app import models``.
    """
    tree = ast.parse(source)
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = _relative_base(module_name, node.level)
                if not base:
                    continue
                if node.module:
                    resolved = ".".join([*base, *node.module.split(".")])
                    if _is_models_module(resolved):
                        violations.add(f"{resolved} (line {node.lineno}, relative)")
                else:
                    for alias in node.names:
                        resolved = ".".join([*base, alias.name])
                        if _is_models_module(resolved):
                            violations.add(f"{resolved} (line {node.lineno}, relative)")
                continue
            if node.module and _is_models_module(node.module):
                violations.add(f"{node.module} (line {node.lineno})")
            elif node.module == "app":
                for alias in node.names:
                    resolved = f"app.{alias.name}"
                    if _is_models_module(resolved):
                        violations.add(f"{resolved} (line {node.lineno})")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_models_module(alias.name):
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
        if (imports := core_model_imports(path.read_text(encoding="utf-8"), _module_name(path)))
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
    assert core_model_imports("from app.models.vault import Vault\n", "app.core.foo") == {"app.models.vault (line 1)"}
    assert core_model_imports("from ..models.incident import IncidentType\n", "app.core.foo") == {
        "app.models.incident (line 1, relative)"
    }
    assert core_model_imports("from .. import models\n", "app.core.foo") == {"app.models (line 1, relative)"}
    assert core_model_imports("from app import models\n", "app.core.foo") == {"app.models (line 1)"}
    assert core_model_imports("from .models import Thing\n", "app.core.foo") == set()
    assert core_model_imports("from app.core import enums\n", "app.core.foo") == set()
