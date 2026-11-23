"""Guard: every public CRUD method that commits must let the caller opt out.

A commit-less caller that expected the flag leaves an uncommitted unique-index entry that
blocks the next session (#1503, PR #1500).
"""

import ast
from pathlib import Path
from typing import NamedTuple

CRUD_DIR = Path(__file__).resolve().parents[2] / "crud"
FIX = "add `commit: bool = True` (keyword-only) and gate the write with `if commit: await session.commit()`"

# Shrink-only debt list: methods that commit on master with no flag. Delete an entry in the PR
# that gives that method its flag; never add one.
DEBT: dict[str, str] = {
    "ai_settings.py": "CRUDAISettings.upsert",
    "base.py": "CRUDBase.create_all CRUDBase.upsert CRUDBase.soft_delete CRUDBase.restore",
    "dweller.py": "CRUDDweller.persist_new_dweller",
    "exploration.py": "CRUDExploration.add_event CRUDExploration.add_loot CRUDExploration.update_stats",
    "game_state.py": "CRUDGameState.pause CRUDGameState.record_presence CRUDGameState.resume CRUDGameState.update_tick",
    "incident.py": "CRUDIncident.resolve CRUDIncident.spread_to_room CRUDIncident.remove CRUDIncident.remove_all_by_vault",
    "item_base.py": "CRUDItem.create_many CRUDItem.unequip CRUDItem.scrap",
    "mixins.py": "CompletionMixin.complete",
    "notification.py": "CRUDNotification.mark_as_read CRUDNotification.mark_all_as_read CRUDNotification.dismiss",
    "objective.py": (
        "CRUDObjective.create_for_vault CRUDObjective.sync_starter_templates "
        "CRUDObjective.sync_achievement_templates CRUDObjective.assign_initial"
    ),
    "quest.py": "CRUDQuest.get_multi_for_vault CRUDQuest.create_quest",
    "relationship.py": "CRUDRelationship.create_with_defaults",
    "room.py": "CRUDRoom.apply_remodel",
    "storage.py": "CRUDStorage.set_medical_supplies",
    "user.py": "CRUDUser.create CRUDUser.create_with_oauth_account CRUDUser.authenticate",
    "user_profile.py": "CRUDUserProfile.create_for_user",
    "vault.py": "CRUDVault.create_with_user_id CRUDVault.delete CRUDVault.restore",
    "vault_slot.py": "CRUDVaultSlot.claim_next",
    "world_location.py": "CRUDWorldLocation.ensure_home_state",
}
# ``default=False`` silently drops the write, so each such method needs a written reason.
# reassign_user predates the convention and its caller depends on the False default; flipping
# it is a behavioural change, not a guard cleanup.
ALLOWED_FALSE_DEFAULTS = frozenset({("conversation.py", "CRUDConversation.reassign_user")})
# Predates the keyword-only convention; existing callers pass it positionally.
POSITIONAL_COMMIT_ALLOWED = frozenset({("world_location.py", "CRUDWorldLocation.link_dweller")})


class Committer(NamedTuple):
    module: str
    method: str
    line: int
    has_flag: bool
    keyword_only: bool
    default: str | None
    annotation: str | None


def _awaits_commit(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "commit"
    )


def _public_methods(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    pairs: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in tree.body:
        owner = node.name if isinstance(node, ast.ClassDef) else ""
        members = node.body if isinstance(node, ast.ClassDef) else [node]
        pairs.extend((owner, m) for m in members if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return [(owner, method) for owner, method in pairs if not method.name.startswith("_")]


def _commit_signature(module: str, source: str) -> list[Committer]:
    """One record per public method awaiting ``.commit()``; ``.flush()``/``.rollback()`` are ignored."""
    records: list[Committer] = []
    for owner, function in _public_methods(ast.parse(source)):
        calls = [node.value for node in ast.walk(function) if _awaits_commit(node)]
        if not calls:
            continue
        args = function.args
        keyword = next((arg for arg in args.kwonlyargs if arg.arg == "commit"), None)
        positional = next((arg for arg in args.args if arg.arg == "commit"), None)
        default: str | None = None
        if keyword is not None:
            node = args.kw_defaults[args.kwonlyargs.index(keyword)]
            default = ast.unparse(node) if node is not None else None
        elif positional is not None:
            index = args.args.index(positional) - (len(args.args) - len(args.defaults))
            default = ast.unparse(args.defaults[index]) if index >= 0 else None
        param = keyword if keyword is not None else positional
        annotation = ast.unparse(param.annotation) if param is not None and param.annotation is not None else None
        records.append(
            Committer(
                module,
                f"{owner}.{function.name}" if owner else function.name,
                calls[0].lineno,
                param is not None,
                keyword is not None,
                default,
                annotation,
            )
        )
    return records


def _inventory() -> list[Committer]:
    return [
        record
        for path in sorted(CRUD_DIR.rglob("*.py"))
        for record in _commit_signature(path.relative_to(CRUD_DIR).as_posix(), path.read_text(encoding="utf-8"))
    ]


def test_extractor_counts_only_awaited_public_commits() -> None:
    source = """
class Alpha:
    async def create(self, session, *, commit: bool = True):
        await session.flush()
        if commit:
            await session.commit()

    async def _private(self, session):
        await session.commit()
"""
    assert [(r.method, r.line, r.keyword_only, r.default) for r in _commit_signature("a.py", source)] == [
        ("Alpha.create", 6, True, "True")
    ]  # flush() and private methods are not commit owners


def test_committing_methods_accept_a_keyword_only_commit_flag() -> None:
    problems: list[str] = []
    for record in _inventory():
        key = (record.module, record.method)
        where = f"app/crud/{record.module}:{record.line} {record.method}"
        if not record.has_flag:
            if record.method not in DEBT.get(record.module, "").split():
                problems.append(f"{where} awaits .commit() but takes no `commit` flag - {FIX}")
        elif not record.keyword_only and key not in POSITIONAL_COMMIT_ALLOWED:
            problems.append(f"{where} takes `commit` positionally instead of keyword-only - {FIX}")
        elif record.default != "True" and key not in ALLOWED_FALSE_DEFAULTS:
            problems.append(f"{where} has `commit` default {record.default!r}, expected `True` - {FIX}")
        elif record.annotation not in (None, "bool"):
            problems.append(f"{where} annotates `commit` as {record.annotation!r}, expected `bool`")
    assert not problems, (
        "CRUD commit ownership must be caller-controlled, or a direct caller leaves the write uncommitted "
        "and blocks the next session on a unique index (#1503).\n" + "\n".join(problems)
    )


def test_debt_list_shrinks_and_never_lists_a_flagged_method() -> None:
    unflagged = {(record.module, record.method) for record in _inventory() if not record.has_flag}
    stale = sorted(
        f"{module}::{method}"
        for module, methods in DEBT.items()
        for method in methods.split()
        if (module, method) not in unflagged
    )
    assert not stale, (
        f"{stale} no longer await .commit() without a flag - delete them from DEBT so the list only shrinks."
    )
