"""Architecture guard: Python enums have one owner, one import path and one dependency direction.

Enums are defined in ``app/core/enums.py``; model modules must not define their own
``StrEnum``/``IntEnum`` and ``app/core`` must not import ``app.models`` (the old
direction created a cycle that only deferred imports hid). Enums are imported from
``app.core.enums`` only: model modules and the retired ``app.schemas.common`` facade
are not import paths for them.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = APP_DIR / "models"
CORE_DIR = APP_DIR / "core"
ENUMS_FILE = CORE_DIR / "enums.py"
COMPAT_ENUM_MODULES = frozenset({"app.schemas.common"})
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


def core_enum_exports() -> set[str]:
    """Top-level names defined in ``app/core/enums.py`` (enums plus their helper constants)."""
    tree = ast.parse(ENUMS_FILE.read_text(encoding="utf-8"))
    names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def compat_enum_imports(source: str, module_name: str, exports: set[str]) -> dict[str, set[str]]:
    """Enum names imported from a non-canonical module, keyed by import target.

    Model modules bind the enums they use for column types, so ``from app.models.incident
    import IncidentType`` still resolves; that incidental re-export is not an import path.
    """
    violations: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            base = _relative_base(module_name, node.level)
            if not base:
                continue
            resolved = ".".join([*base, *node.module.split(".")]) if node.module else None
        else:
            resolved = node.module
        if resolved is None or not (_is_models_module(resolved) or resolved in COMPAT_ENUM_MODULES):
            continue
        moved = {alias.name for alias in node.names if alias.name in exports}
        if moved:
            violations.setdefault(f"{resolved} (line {node.lineno})", set()).update(moved)
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


def test_enums_are_imported_from_core_only() -> None:
    exports = core_enum_exports()
    violations = {
        str(path.relative_to(APP_DIR)): found
        for path in APP_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
        and path != ENUMS_FILE
        and (found := compat_enum_imports(path.read_text(encoding="utf-8"), _module_name(path), exports))
    }

    assert not violations, (
        "Enums must be imported from app.core.enums, not from app.models or app.schemas.common:\n  "
        + "\n  ".join(
            f"{path}: {sorted(names)} via {target}"
            for path, targets in sorted(violations.items())
            for target, names in sorted(targets.items())
        )
    )


def test_compat_enum_module_is_removed() -> None:
    assert not (APP_DIR / "schemas" / "common.py").exists(), (
        "app/schemas/common.py is retired: import enums from app.core.enums and serializers from app.utils.serialize"
    )


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


def test_compat_enum_detector_catches_the_old_shapes() -> None:
    exports = {"IncidentType", "GenderEnum"}

    assert compat_enum_imports("from app.models.incident import IncidentType\n", "app.services.x", exports) == {
        "app.models.incident (line 1)": {"IncidentType"}
    }
    assert compat_enum_imports("from app.schemas.common import GenderEnum\n", "app.tests.x", exports) == {
        "app.schemas.common (line 1)": {"GenderEnum"}
    }
    assert compat_enum_imports("from ..models.incident import IncidentType\n", "app.services.x", exports) == {
        "app.models.incident (line 1)": {"IncidentType"}
    }
    assert compat_enum_imports("from app.models.incident import Incident\n", "app.services.x", exports) == {}
    assert compat_enum_imports("from app.core.enums import IncidentType\n", "app.services.x", exports) == {}
