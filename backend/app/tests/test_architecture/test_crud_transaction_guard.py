"""Ratchet for commit/rollback calls inside the CRUD layer.

CRUD must never commit or roll back. Each ``(module, function, kind)`` key carries its
observed call count, so a new key, a grown count or a stale entry all fail the suite;
shrink the baseline when a function stops committing, never grow it by hand.
"""

import ast
import collections
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]
CRUD_DIR = APP_DIR / "crud"
TRANSACTION_CALLS = frozenset({"commit", "rollback"})

CRUD_TRANSACTION_BASELINE: dict[tuple[str, str, str], int] = {
    ("account_merge.py", "CRUDAccountMerge.create", "commit"): 1,
    ("ai_settings.py", "CRUDAISettings.upsert", "commit"): 2,
    ("ai_settings.py", "CRUDAISettings.upsert", "rollback"): 1,
    ("base.py", "CRUDBase.create", "commit"): 1,
    ("base.py", "CRUDBase.create", "rollback"): 1,
    ("base.py", "CRUDBase.create_all", "commit"): 1,
    ("base.py", "CRUDBase.create_all", "rollback"): 1,
    ("base.py", "CRUDBase.delete", "commit"): 2,
    ("base.py", "CRUDBase.restore", "commit"): 1,
    ("base.py", "CRUDBase.soft_delete", "commit"): 1,
    ("base.py", "CRUDBase.update", "commit"): 1,
    ("base.py", "CRUDBase.upsert", "commit"): 1,
    ("chat_message.py", "CRUDChatMessage.reassign_user", "commit"): 1,
    ("conversation.py", "CRUDConversation.reassign_user", "commit"): 1,
    ("dweller.py", "CRUDDweller.persist_new_dweller", "commit"): 1,
    ("expedition_run.py", "CRUDExpeditionRun.create_run", "rollback"): 1,
    ("exploration.py", "CRUDExploration.add_event", "commit"): 1,
    ("exploration.py", "CRUDExploration.add_loot", "commit"): 1,
    ("exploration.py", "CRUDExploration.update_stats", "commit"): 1,
    ("game_state.py", "CRUDGameState.get_or_create", "commit"): 1,
    ("game_state.py", "CRUDGameState.pause", "commit"): 1,
    ("game_state.py", "CRUDGameState.record_presence", "commit"): 1,
    ("game_state.py", "CRUDGameState.resume", "commit"): 1,
    ("game_state.py", "CRUDGameState.update_tick", "commit"): 1,
    ("incident.py", "CRUDIncident.create", "commit"): 1,
    ("incident.py", "CRUDIncident.remove", "commit"): 1,
    ("incident.py", "CRUDIncident.remove_all_by_vault", "commit"): 1,
    ("incident.py", "CRUDIncident.resolve", "commit"): 1,
    ("incident.py", "CRUDIncident.spread_to_room", "commit"): 1,
    ("item_base.py", "CRUDItem.create_many", "commit"): 1,
    ("item_base.py", "CRUDItem.equip", "commit"): 1,
    ("llm_interaction.py", "CRUDLLMInteraction.reassign_user", "commit"): 1,
    ("mixins.py", "CompletionMixin.complete", "commit"): 1,
    ("mixins.py", "CompletionMixin.complete", "rollback"): 1,
    ("notification.py", "CRUDNotification.create", "commit"): 1,
    ("notification.py", "CRUDNotification.dismiss", "commit"): 1,
    ("notification.py", "CRUDNotification.mark_all_as_read", "commit"): 1,
    ("notification.py", "CRUDNotification.mark_as_read", "commit"): 1,
    ("notification.py", "CRUDNotification.reassign_user", "commit"): 1,
    ("oauth_account.py", "CRUDOAuthAccount.delete_link", "commit"): 1,
    ("oauth_account.py", "CRUDOAuthAccount.link_to_user", "commit"): 1,
    ("oauth_account.py", "CRUDOAuthAccount.link_to_user", "rollback"): 1,
    ("oauth_account.py", "CRUDOAuthAccount.reassign_user", "commit"): 1,
    ("objective.py", "CRUDObjective.assign_initial", "commit"): 1,
    ("objective.py", "CRUDObjective.assign_initial", "rollback"): 1,
    ("objective.py", "CRUDObjective.create_for_vault", "commit"): 1,
    ("objective.py", "CRUDObjective.sync_achievement_templates", "commit"): 1,
    ("objective.py", "CRUDObjective.sync_starter_templates", "commit"): 1,
    ("quest.py", "CRUDQuest.assign_to_vault", "commit"): 1,
    ("quest.py", "CRUDQuest.create_quest", "commit"): 1,
    ("quest.py", "CRUDQuest.get_multi_for_vault", "commit"): 1,
    ("relationship.py", "CRUDRelationship.create_with_defaults", "commit"): 1,
    ("room.py", "CRUDRoom.apply_remodel", "commit"): 1,
    ("storage.py", "CRUDStorage.create_for_vault", "commit"): 1,
    ("storage.py", "CRUDStorage.set_max_space", "commit"): 1,
    ("storage.py", "CRUDStorage.set_medical_supplies", "commit"): 1,
    ("user.py", "CRUDUser.authenticate", "commit"): 1,
    ("user.py", "CRUDUser.create", "commit"): 1,
    ("user.py", "CRUDUser.create", "rollback"): 1,
    ("user_profile.py", "CRUDUserProfile.delete_for_user", "commit"): 1,
    ("user_profile.py", "CRUDUserProfile.increment_statistic", "commit"): 1,
    ("user_profile.py", "CRUDUserProfile.reassign_user", "commit"): 1,
    ("vault.py", "CRUDVault.delete", "commit"): 2,
    ("vault.py", "CRUDVault.reassign_user", "commit"): 1,
    ("vault.py", "CRUDVault.restore", "commit"): 1,
    ("vault_slot.py", "CRUDVaultSlot.claim_next", "commit"): 1,
    ("world_location.py", "CRUDWorldLocation._promote_to_home_marker", "commit"): 1,
    ("world_location.py", "CRUDWorldLocation.ensure_home_state", "commit"): 1,
    ("world_location.py", "CRUDWorldLocation.get_or_create_home_marker", "commit"): 1,
    ("world_location.py", "CRUDWorldLocation.get_or_create_home_marker", "rollback"): 1,
    ("world_location.py", "CRUDWorldLocation.get_or_create_location", "commit"): 1,
    ("world_location.py", "CRUDWorldLocation.get_or_create_location", "rollback"): 1,
    ("world_location.py", "CRUDWorldLocation.get_or_create_state", "commit"): 1,
    ("world_location.py", "CRUDWorldLocation.get_or_create_state", "rollback"): 1,
    ("world_location.py", "CRUDWorldLocation.link_dweller", "commit"): 3,
    ("world_location.py", "CRUDWorldLocation.link_dweller", "rollback"): 1,
}
# SERVICE_LAYER.md sanctions exactly two legacy owners: ``CRUDBase`` and
# ``CRUDWorldLocation.get_or_create*`` / ``link_dweller`` (historical name: CRUDWastelandLocation).
SANCTIONED_BASE_CLASS = "CRUDBase"
# Shrink-only: these are the only owners allowed to commit in world_location.py. A baseline
# entry may disappear as the debt is paid, but nothing outside this set may ever appear.
SANCTIONED_WORLD_LOCATION_CALLS = frozenset(
    {
        ("world_location.py", "CRUDWorldLocation.get_or_create_location", "commit"),
        ("world_location.py", "CRUDWorldLocation.get_or_create_location", "rollback"),
        ("world_location.py", "CRUDWorldLocation.get_or_create_state", "commit"),
        ("world_location.py", "CRUDWorldLocation.get_or_create_state", "rollback"),
        ("world_location.py", "CRUDWorldLocation.get_or_create_home_marker", "commit"),
        ("world_location.py", "CRUDWorldLocation.get_or_create_home_marker", "rollback"),
        ("world_location.py", "CRUDWorldLocation.link_dweller", "commit"),
        ("world_location.py", "CRUDWorldLocation.link_dweller", "rollback"),
        # Private helper of the sanctioned get_or_create* family (called from those paths only).
        ("world_location.py", "CRUDWorldLocation._promote_to_home_marker", "commit"),
        # Legacy public wrapper over get_or_create_state that still commits; not named in
        # SERVICE_LAYER.md. Recorded here so it cannot spread, flagged for cleanup in #1499.
        ("world_location.py", "CRUDWorldLocation.ensure_home_state", "commit"),
    }
)
BASE_COMMIT_KIND = "commit"


def _transaction_calls(source: str) -> dict[tuple[str, str], int]:
    """Count awaited ``commit``/``rollback`` calls per owner.

    The key carries the enclosing class (``CRUDUser.create``) so two classes cannot share a
    counter; a nested callable is its own owner (``CRUDUser.create.<locals>.retry``).
    """
    tree = ast.parse(source)
    found: collections.Counter[tuple[str, str]] = collections.Counter()

    def count_owner(node: ast.FunctionDef | ast.AsyncFunctionDef, owner: str) -> None:
        pending = list(node.body)
        while pending:
            child = pending.pop()
            # A nested callable owns its body: recurse under a qualified name so its writes stay
            # measurable without being attributed to the enclosing function.
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                count_owner(child, f"{owner}.<locals>.{child.name}")
                continue
            if isinstance(child, ast.ClassDef):
                for member in child.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        count_owner(member, f"{owner}.<locals>.{child.name}.{member.name}")
                continue
            if isinstance(child, ast.Lambda):
                continue
            if (
                isinstance(child, ast.Await)
                and isinstance(child.value, ast.Call)
                and isinstance(child.value.func, ast.Attribute)
                and child.value.func.attr in TRANSACTION_CALLS
            ):
                found[owner, child.value.func.attr] += 1
            pending.extend(ast.iter_child_nodes(child))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    count_owner(member, f"{node.name}.{member.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            count_owner(node, node.name)
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


def test_counter_keeps_classes_apart() -> None:
    """Two classes sharing a method name must not share a counter, or one gaining a commit
    while the other loses one leaves the total unchanged.
    """
    source = """
class Alpha:
    async def create(self, session):
        await session.commit()

class Beta:
    async def create(self, session):
        await session.commit()
        await session.commit()
"""
    assert _transaction_calls(source) == {("Alpha.create", "commit"): 1, ("Beta.create", "commit"): 2}


def test_counter_attributes_nested_callable_transactions() -> None:
    """A transaction call inside an inner ``async def`` must have its own owner key."""
    source = """
class Alpha:
    async def create(self, session):
        async def retry(saved):
            await session.rollback()
            await session.commit()

        await retry(1)


async def module_helper(session):
    async def reopen():
        await session.commit()

    await reopen()
    await session.commit()
"""
    assert _transaction_calls(source) == {
        ("Alpha.create.<locals>.retry", "rollback"): 1,
        ("Alpha.create.<locals>.retry", "commit"): 1,
        ("module_helper", "commit"): 1,
        ("module_helper.<locals>.reopen", "commit"): 1,
    }


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
    """Ownership check, shrink-only: entries may disappear, unsanctioned owners may not appear."""
    baseline_keys = set(CRUD_TRANSACTION_BASELINE)

    base_functions = _functions_in_class((CRUD_DIR / "base.py").read_text(encoding="utf-8"), SANCTIONED_BASE_CLASS)
    allowed_base = {
        (module, owner, kind)
        for module, owner, kind in baseline_keys
        if module == "base.py"
        and owner.startswith(f"{SANCTIONED_BASE_CLASS}.")
        and owner.split(".", 1)[1] in base_functions
    }
    unsanctioned_base = sorted(key for key in baseline_keys if key[0] == "base.py" and key not in allowed_base)
    assert not unsanctioned_base, (
        f"app/crud/base.py commits outside {SANCTIONED_BASE_CLASS}: {unsanctioned_base}. "
        "CRUD must flush; only the sanctioned legacy base may commit."
    )

    world_location_calls = {key for key in baseline_keys if key[0] == "world_location.py"}
    unsanctioned = sorted(world_location_calls - SANCTIONED_WORLD_LOCATION_CALLS)
    assert not unsanctioned, (
        "world_location.py commits outside CRUDWorldLocation.get_or_create*/link_dweller: "
        f"{unsanctioned}. CRUD must flush; only the sanctioned legacy owners may commit."
    )
