"""Guard: every public CRUD method that commits must let the caller opt out.

A direct caller that expected the flag leaves an uncommitted unique-index entry behind and blocks
the next session (#1503).
"""

import ast
from pathlib import Path
from typing import NamedTuple

CRUD_DIR = Path(__file__).resolve().parents[2] / "crud"
FIX = "add `commit: bool = True` (keyword-only) and gate the write with `if commit: await session.commit()`"

# Shrink-only: delete an entry in the PR that gives that method its flag; never add one.
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
# A False default silently drops the write, so each such method needs a written reason:
# reassign_user predates the convention and its caller depends on the False default.
ALLOWED_FALSE_DEFAULTS = frozenset({("conversation.py", "CRUDConversation.reassign_user")})
# Predates keyword-only; existing callers pass it positionally.
POSITIONAL_COMMIT_ALLOWED = frozenset({("world_location.py", "CRUDWorldLocation.link_dweller")})


class Committer(NamedTuple):
    module: str
    method: str
    line: int
    kind: str  # "keyword" | "positional" | "missing"
    default: str | None
    annotation: str | None


def _commit_call(node: ast.AST) -> ast.Call | None:
    if (
        isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "commit"
    ):
        return node.value
    return None


def _public_methods(tree: ast.Module):
    for node in tree.body:
        owner = node.name if isinstance(node, ast.ClassDef) else ""
        for member in node.body if isinstance(node, ast.ClassDef) else [node]:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not member.name.startswith("_"):
                yield owner, member


def _records(module: str, source: str) -> list[Committer]:
    """One record per public method awaiting ``.commit()``; ``.flush()``/``.rollback()`` are ignored."""
    records: list[Committer] = []
    for owner, function in _public_methods(ast.parse(source)):
        line = next((call.lineno for call in map(_commit_call, ast.walk(function)) if call is not None), None)
        if line is None:
            continue
        args = function.args
        keyword = next((arg for arg in args.kwonlyargs if arg.arg == "commit"), None)
        positional = next((arg for arg in args.args if arg.arg == "commit"), None)
        param = keyword if keyword is not None else positional
        node = None
        kind = "missing"
        if keyword is not None:
            kind = "keyword"
            node = args.kw_defaults[args.kwonlyargs.index(keyword)]
        elif positional is not None:
            kind = "positional"
            index = args.args.index(positional) - (len(args.args) - len(args.defaults))
            node = args.defaults[index] if index >= 0 else None
        records.append(
            Committer(
                module,
                f"{owner}.{function.name}" if owner else function.name,
                line,
                kind,
                ast.unparse(node) if node is not None else None,
                ast.unparse(param.annotation) if param is not None and param.annotation is not None else None,
            )
        )
    return records


def _inventory() -> list[Committer]:
    return [
        record
        for path in sorted(CRUD_DIR.rglob("*.py"))
        for record in _records(path.relative_to(CRUD_DIR).as_posix(), path.read_text(encoding="utf-8"))
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
    assert [(r.method, r.line, r.kind, r.default) for r in _records("a.py", source)] == [
        ("Alpha.create", 6, "keyword", "True")
    ]  # flush() and private methods are not commit owners


def test_committing_methods_take_a_keyword_only_true_commit_flag() -> None:
    problems: list[str] = []
    inventory = _inventory()
    for record in inventory:
        key = (record.module, record.method)
        where = f"app/crud/{record.module}:{record.line} {record.method}"
        if record.kind == "missing":
            if record.method not in DEBT.get(record.module, "").split():
                problems.append(f"{where} awaits .commit() but takes no `commit` flag - {FIX}")
        elif record.kind == "positional" and key not in POSITIONAL_COMMIT_ALLOWED:
            problems.append(f"{where} takes `commit` positionally instead of keyword-only - {FIX}")
        elif record.default != "True" and key not in ALLOWED_FALSE_DEFAULTS:
            problems.append(f"{where} has `commit` default {record.default!r}, expected `True` - {FIX}")
        elif record.annotation not in (None, "bool"):
            problems.append(f"{where} annotates `commit` as {record.annotation!r}, expected `bool`")
    stale = sorted(
        f"{module}::{method}"
        for module, methods in DEBT.items()
        for method in methods.split()
        if (module, method) not in {(r.module, r.method) for r in inventory if r.kind == "missing"}
    )
    if stale:
        problems.append(
            f"{stale} no longer await .commit() without a flag - delete them from DEBT so the list only shrinks."
        )
    assert not problems, (
        "CRUD commit ownership must be caller-controlled, or a direct caller leaves the write uncommitted "
        "and blocks the next session on a unique index (#1503).\n" + "\n".join(problems)
    )
