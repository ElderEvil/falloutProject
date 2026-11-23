"""Ratchet for commit/rollback calls inside the CRUD layer.

SERVICE_LAYER.md declares the target state: *CRUD never commits and never rolls back; it only
executes queries and flushes*. Today 25 legacy CRUD modules still own transactions, so this guard
freezes the current inventory **per function and per call count** instead of blessing whole files.

Why counts: a function that already commits twice can silently gain a third commit and stay
"green" under a key-set ratchet, which is exactly the regression that turns one transaction
boundary into several. Each `(module, function, kind)` key therefore carries its observed call
count; any new key, any count growth and any stale (shrunken) entry fails the suite. Shrink the
baseline whenever a function stops committing - never grow it by hand.
"""

import ast
import collections
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
CRUD_DIR = APP_DIR / "crud"
TRANSACTION_CALLS = frozenset({"commit", "rollback"})

CRUD_TRANSACTION_BASELINE: dict[tuple[str, str, str], int] = {
    ("account_merge.py", "create", "commit"): 1,
    ("ai_settings.py", "upsert", "commit"): 2,
    ("ai_settings.py", "upsert", "rollback"): 1,
    ("base.py", "create", "commit"): 1,
    ("base.py", "create", "rollback"): 1,
    ("base.py", "create_all", "commit"): 1,
    ("base.py", "create_all", "rollback"): 1,
    ("base.py", "delete", "commit"): 2,
    ("base.py", "restore", "commit"): 1,
    ("base.py", "soft_delete", "commit"): 1,
    ("base.py", "update", "commit"): 1,
    ("base.py", "upsert", "commit"): 1,
    ("chat_message.py", "reassign_user", "commit"): 1,
    ("conversation.py", "reassign_user", "commit"): 1,
    ("dweller.py", "persist_new_dweller", "commit"): 1,
    ("expedition_run.py", "create_run", "rollback"): 1,
    ("exploration.py", "add_event", "commit"): 1,
    ("exploration.py", "add_loot", "commit"): 1,
    ("exploration.py", "update_stats", "commit"): 1,
    ("game_state.py", "get_or_create", "commit"): 1,
    ("game_state.py", "pause", "commit"): 1,
    ("game_state.py", "record_presence", "commit"): 1,
    ("game_state.py", "resume", "commit"): 1,
    ("game_state.py", "update_tick", "commit"): 1,
    ("incident.py", "create", "commit"): 1,
    ("incident.py", "remove", "commit"): 1,
    ("incident.py", "remove_all_by_vault", "commit"): 1,
    ("incident.py", "resolve", "commit"): 1,
    ("incident.py", "spread_to_room", "commit"): 1,
    ("item_base.py", "create_many", "commit"): 1,
    ("item_base.py", "equip", "commit"): 1,
    ("item_base.py", "scrap", "commit"): 1,
    ("item_base.py", "unequip", "commit"): 1,
    ("llm_interaction.py", "reassign_user", "commit"): 1,
    ("mixins.py", "complete", "commit"): 1,
    ("mixins.py", "complete", "rollback"): 1,
    ("notification.py", "create", "commit"): 1,
    ("notification.py", "dismiss", "commit"): 1,
    ("notification.py", "mark_all_as_read", "commit"): 1,
    ("notification.py", "mark_as_read", "commit"): 1,
    ("notification.py", "reassign_user", "commit"): 1,
    ("oauth_account.py", "delete_link", "commit"): 1,
    ("oauth_account.py", "link_to_user", "commit"): 1,
    ("oauth_account.py", "link_to_user", "rollback"): 1,
    ("oauth_account.py", "reassign_user", "commit"): 1,
    ("objective.py", "assign_initial", "commit"): 1,
    ("objective.py", "assign_initial", "rollback"): 1,
    ("objective.py", "create_for_vault", "commit"): 1,
    ("objective.py", "sync_achievement_templates", "commit"): 1,
    ("objective.py", "sync_starter_templates", "commit"): 1,
    ("quest.py", "assign_to_vault", "commit"): 1,
    ("quest.py", "create_quest", "commit"): 1,
    ("quest.py", "get_multi_for_vault", "commit"): 1,
    ("relationship.py", "create_with_defaults", "commit"): 1,
    ("room.py", "apply_remodel", "commit"): 1,
    ("storage.py", "create_for_vault", "commit"): 1,
    ("storage.py", "set_max_space", "commit"): 1,
    ("storage.py", "set_medical_supplies", "commit"): 1,
    ("user.py", "authenticate", "commit"): 1,
    ("user.py", "create", "commit"): 1,
    ("user.py", "create", "rollback"): 1,
    ("user.py", "create_with_oauth_account", "commit"): 1,
    ("user.py", "create_with_oauth_account", "rollback"): 1,
    ("user_profile.py", "delete_for_user", "commit"): 1,
    ("user_profile.py", "increment_statistic", "commit"): 1,
    ("user_profile.py", "reassign_user", "commit"): 1,
    ("vault.py", "create_with_user_id", "commit"): 1,
    ("vault.py", "create_with_user_id", "rollback"): 2,
    ("vault.py", "delete", "commit"): 2,
    ("vault.py", "reassign_user", "commit"): 1,
    ("vault.py", "restore", "commit"): 1,
    ("vault_slot.py", "claim_next", "commit"): 1,
    ("world_location.py", "_promote_to_home_marker", "commit"): 1,
    ("world_location.py", "ensure_home_state", "commit"): 1,
    ("world_location.py", "get_or_create_home_marker", "commit"): 1,
    ("world_location.py", "get_or_create_home_marker", "rollback"): 1,
    ("world_location.py", "get_or_create_location", "commit"): 1,
    ("world_location.py", "get_or_create_location", "rollback"): 1,
    ("world_location.py", "get_or_create_state", "commit"): 1,
    ("world_location.py", "get_or_create_state", "rollback"): 1,
    ("world_location.py", "link_dweller", "commit"): 3,
    ("world_location.py", "link_dweller", "rollback"): 1,
}
# SERVICE_LAYER.md sanctions exactly two legacy owners: ``CRUDBase`` and
# ``CRUDWorldLocation.get_or_create*`` / ``link_dweller`` (historical name: CRUDWastelandLocation).
SANCTIONED_BASE_CLASS = "CRUDBase"
SANCTIONED_WORLD_LOCATION_CALLS = frozenset(
    {
        ("world_location.py", "get_or_create_location", "commit"),
        ("world_location.py", "get_or_create_location", "rollback"),
        ("world_location.py", "get_or_create_state", "commit"),
        ("world_location.py", "get_or_create_state", "rollback"),
        ("world_location.py", "get_or_create_home_marker", "commit"),
        ("world_location.py", "get_or_create_home_marker", "rollback"),
        ("world_location.py", "link_dweller", "commit"),
        ("world_location.py", "link_dweller", "rollback"),
    }
)
BASE_COMMIT_KIND = "commit"


def _transaction_calls(source: str) -> dict[tuple[str, str], int]:
    """Count awaited ``commit``/``rollback`` calls per function, ignoring nested callables."""
    found: collections.Counter[tuple[str, str]] = collections.Counter()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        pending = list(node.body)
        while pending:
            child = pending.pop()
            # A nested callable owns its body; do not attribute its writes to the enclosing function.
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if (
                isinstance(child, ast.Await)
                and isinstance(child.value, ast.Call)
                and isinstance(child.value.func, ast.Attribute)
                and child.value.func.attr in TRANSACTION_CALLS
            ):
                found[node.name, child.value.func.attr] += 1
            pending.extend(ast.iter_child_nodes(child))
    return dict(found)


def _measured_inventory() -> dict[tuple[str, str, str], int]:
    measured: dict[tuple[str, str, str], int] = {}
    for path in sorted(CRUD_DIR.rglob("*.py")):
        rel = path.relative_to(CRUD_DIR).as_posix()
        for (function, kind), count in _transaction_calls(path.read_text(encoding="utf-8")).items():
            measured[rel, function, kind] = count
    return measured


def _functions_in_class(source: str, class_name: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            names.update(
                child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return names


def test_crud_transaction_inventory_is_frozen() -> None:
    measured = _measured_inventory()
    new_keys = sorted(set(measured) - set(CRUD_TRANSACTION_BASELINE))
    grown_keys = sorted(
        key for key in set(measured) & set(CRUD_TRANSACTION_BASELINE) if measured[key] > CRUD_TRANSACTION_BASELINE[key]
    )
    stale_keys = sorted(
        key
        for key in set(CRUD_TRANSACTION_BASELINE)
        if key not in measured or measured[key] < CRUD_TRANSACTION_BASELINE[key]
    )
    messages = [
        f"{module}::{function} now awaits {kind}() {measured[module, function, kind]}x "
        f"but the baseline allows 0 - CRUD must flush, not own transactions"
        for module, function, kind in new_keys
    ]
    messages += [
        f"{module}::{function} awaits {kind}() {measured[key]}x, baseline allows "
        f"{CRUD_TRANSACTION_BASELINE[key]} - adding commits to an existing boundary is forbidden"
        for key in grown_keys
        for module, function, kind in [key]
    ]
    messages += [
        f"{module}::{function} no longer awaits {kind}() as often "
        f"(baseline {CRUD_TRANSACTION_BASELINE[key]}, measured {measured.get(key, 0)}) - "
        f"shrink CRUD_TRANSACTION_BASELINE to the measured count"
        for key in stale_keys
        for module, function, kind in [key]
    ]
    assert not messages, (
        "CRUD transaction surface changed (baseline covers "
        f"{sum(CRUD_TRANSACTION_BASELINE.values())} calls across {len(CRUD_TRANSACTION_BASELINE)} keys).\n"
        "When you fix a commit, lower or delete its baseline entry.\n" + "\n".join(messages)
    )


def test_only_the_sanctioned_legacy_owners_commit() -> None:
    baseline_keys = set(CRUD_TRANSACTION_BASELINE)
    base_calls = {key for key in baseline_keys if key[0] == "base.py"}
    assert any(kind == BASE_COMMIT_KIND for _, _, kind in base_calls), (
        "the CRUDBase commit exception vanished from the baseline; shrink it"
    )

    base_functions = _functions_in_class((CRUD_DIR / "base.py").read_text(encoding="utf-8"), SANCTIONED_BASE_CLASS)
    unsanctioned = sorted({name for _, name, _ in base_calls if name not in base_functions})
    assert not unsanctioned, (
        f"app/crud/base.py commits outside {SANCTIONED_BASE_CLASS}: {unsanctioned}. "
        "CRUD must flush; only the sanctioned legacy base may commit."
    )

    missing = sorted(SANCTIONED_WORLD_LOCATION_CALLS - baseline_keys)
    assert not missing, (
        f"the sanctioned CRUDWorldLocation get_or_create*/link_dweller commits are missing from the baseline: {missing}"
    )
