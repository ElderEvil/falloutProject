"""Architecture guard for catalog-backed item construction (app/utils/item_factory.py).

``Weapon``, ``Outfit``, ``Junk`` and ``Item`` all carry columns whose real values live in
the data catalog, and every one of those columns has a benign default (``0``/``None``). A
direct constructor call therefore compiles, persists, serializes and renders exactly like a
correct item — it just silently drops whatever the catalog would have filled. That is how
outfits shipped with no SPECIAL bonuses (see the backfill migration
``2026_09_19_0002``), and no type checker or unit test could see it because ``0`` is a legal
"no bonus" value.

Every direct construction outside the factory is counted in ``ITEM_CONSTRUCTION_BASELINE``
and must shrink as call sites migrate. Counts, not mere presence: a second bypass inside an
already-listed module would otherwise collapse into the same ``(path, model)`` entry and
slip through. A count above the baseline fails, and a count below it fails as stale so the
list cannot silently rot.
"""

import ast
from collections import Counter
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
FACTORY = APP_DIR / "utils" / "item_factory.py"
GUARDED_MODELS = frozenset({"Weapon", "Outfit", "Junk", "Item"})
EXCLUDED_DIRS = frozenset({"tests", "alembic", "__pycache__"})

# Pre-existing direct constructions, keyed by (module, model) -> call count.
# Shrink these numbers with each migration batch; never raise them.
ITEM_CONSTRUCTION_BASELINE: dict[tuple[str, str], int] = {
    ("crud/item_base.py", "Junk"): 2,  # scrap byproducts, not catalog-backed
    ("services/reward_service.py", "Item"): 1,  # generic reward item
    ("services/reward_service.py", "Junk"): 1,  # duplicate of item_factory.build_junk
    ("services/vault_service.py", "Junk"): 1,  # _seed_boosted_junk
    ("services/vault_service.py", "Weapon"): 1,  # boosted loadout, hardcoded damage
}


def _direct_constructions(source: str) -> Counter[str]:
    """How often each guarded model is constructed by a bare call in this module."""
    counts: Counter[str] = Counter()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in GUARDED_MODELS:
            counts[func.id] += 1
        elif isinstance(func, ast.Attribute) and func.attr in GUARDED_MODELS:
            counts[func.attr] += 1
    return counts


def _guarded_modules() -> list[Path]:
    """Every app module that must build catalog-backed items through the factory."""
    modules: list[Path] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        relative = path.relative_to(APP_DIR)
        if path != FACTORY and not any(part in EXCLUDED_DIRS for part in relative.parts):
            modules.append(path)
    return modules


def _found_constructions() -> dict[tuple[str, str], int]:
    found: dict[tuple[str, str], int] = {}
    for path in _guarded_modules():
        relative = path.relative_to(APP_DIR).as_posix()
        for model, count in _direct_constructions(path.read_text(encoding="utf-8")).items():
            found[(relative, model)] = count
    return found


def test_catalog_backed_items_are_built_through_the_shared_factory() -> None:
    """Only app/utils/item_factory.py may construct catalog-backed item models."""
    found = _found_constructions()

    messages = []
    for (path, model), count in sorted(found.items()):
        allowed = ITEM_CONSTRUCTION_BASELINE.get((path, model), 0)
        if count > allowed:
            messages.append(
                f"{path} constructs {model} {count}x (baseline {allowed}); build it via app.utils.item_factory"
            )
    for (path, model), allowed in sorted(ITEM_CONSTRUCTION_BASELINE.items()):
        remaining = found.get((path, model), 0)
        if remaining < allowed:
            messages.append(f"baseline entry {path} / {model} is stale ({remaining} left of {allowed}); lower it")

    assert not messages, "Catalog-backed item construction escaped the factory:\n" + "\n".join(messages)
