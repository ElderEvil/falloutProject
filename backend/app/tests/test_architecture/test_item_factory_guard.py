"""Architecture guard for catalog-backed item construction (app/utils/item_factory.py).

``Weapon``, ``Outfit``, ``Junk`` and ``Item`` all carry columns whose real values live in
the data catalog, and every one of those columns has a benign default (``0``/``None``). A
direct constructor call therefore compiles, persists, serializes and renders exactly like a
correct item — it just silently drops whatever the catalog would have filled. That is how
outfits shipped with no SPECIAL bonuses (see the backfill migration
``2026_09_19_0002``), and no type checker or unit test could see it because ``0`` is a legal
"no bonus" value.

Every direct construction outside the factory is recorded in ``ITEM_CONSTRUCTION_BASELINE``
and must shrink as call sites migrate. A new bypass fails the suite, and a baseline entry
with no remaining violation also fails, so the list stays honest.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
FACTORY = APP_DIR / "utils" / "item_factory.py"
GUARDED_MODELS = frozenset({"Weapon", "Outfit", "Junk", "Item"})
EXCLUDED_DIRS = frozenset({"tests", "alembic", "__pycache__"})

# Pre-existing direct constructions. Shrink this list with each migration batch; never extend it.
ITEM_CONSTRUCTION_BASELINE = frozenset(
    {
        ("crud/item_base.py", "Junk"),  # scrap byproducts, not catalog-backed
        ("services/reward_service.py", "Item"),  # generic reward item
        ("services/reward_service.py", "Junk"),  # duplicate of item_factory.build_junk
        ("services/vault_service.py", "Junk"),  # _seed_boosted_junk
        ("services/vault_service.py", "Weapon"),  # boosted loadout, hardcoded damage
    }
)


def _direct_constructions(source: str) -> set[str]:
    """Model names constructed by a bare call in this module (``Outfit(...)``)."""
    models: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in GUARDED_MODELS:
            models.add(func.id)
        elif isinstance(func, ast.Attribute) and func.attr in GUARDED_MODELS:
            models.add(func.attr)
    return models


def _guarded_modules() -> list[Path]:
    """Every app module that must build catalog-backed items through the factory."""
    modules: list[Path] = []
    for path in sorted(APP_DIR.rglob("*.py")):
        relative = path.relative_to(APP_DIR)
        if path != FACTORY and not any(part in EXCLUDED_DIRS for part in relative.parts):
            modules.append(path)
    return modules


def test_catalog_backed_items_are_built_through_the_shared_factory() -> None:
    """Only app/utils/item_factory.py may construct catalog-backed item models."""
    found = {
        (path.relative_to(APP_DIR).as_posix(), model)
        for path in _guarded_modules()
        for model in _direct_constructions(path.read_text(encoding="utf-8"))
    }

    new_violations = found - ITEM_CONSTRUCTION_BASELINE
    stale_entries = ITEM_CONSTRUCTION_BASELINE - found
    messages = [
        f"{path} constructs {model} directly; build it via app.utils.item_factory"
        for path, model in sorted(new_violations)
    ]
    messages += [f"baseline entry {path} / {model} is stale; remove it" for path, model in sorted(stale_entries)]
    assert not messages, "Catalog-backed item construction escaped the factory:\n" + "\n".join(messages)
