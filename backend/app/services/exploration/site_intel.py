"""Derived site intel: the check profile a site advertises to would-be couriers.

Pure projection of authored site content — no I/O, no rolls. The player-facing
promise: a site's intel can never drift from what its rooms actually check,
because it is computed from the same definition the run resolves.
"""

from app.schemas.expedition import (
    NodeBranch,
    NodeOption,
    SiteCheckIntel,
    SiteDefinition,
    SiteIntel,
    SiteNode,
)


def _branch_pulls_combat(branch: NodeBranch) -> bool:
    return bool(branch.combat_enemies)


def _option_bloodless(option: NodeOption) -> bool:
    """This option settles the room without a fight on either outcome."""
    return not _branch_pulls_combat(option.success) and not _branch_pulls_combat(option.failure)


def _room_bloodless(node: SiteNode) -> bool:
    """A path through this room that fights nobody exists."""
    if node.kind == "combat":
        return False
    if not node.options:
        # trivia (answer right, no fight), finale, and bare traps — damage
        # maybe, but nobody shoots.
        return True
    return any(_option_bloodless(option) for option in node.options)


def _node_checks(node: SiteNode) -> list[SiteCheckIntel]:
    """Advertised checks on one node: its options, plus a finale's terminal."""
    checks: list[SiteCheckIntel] = [
        SiteCheckIntel(
            stat=option.stat,
            difficulty=option.difficulty,
            label=option.label,
            bloodless=_option_bloodless(option),
        )
        for option in node.options
        if option.stat and option.difficulty
    ]
    if node.kind == "finale" and node.stat and node.difficulty:
        checks.append(SiteCheckIntel(stat=node.stat, difficulty=node.difficulty, label="Terminal", bloodless=True))
    return checks


def site_intel(site: SiteDefinition, *, spatial: bool) -> SiteIntel:
    """Project the check profile of the content this visit will actually play.

    Spatial visits resolve the single encounter; legacy runs walk every room.
    Checks dedupe on (stat, difficulty) — three doors locking the same way is
    one fact, not three.
    """
    if site.encounter is not None and spatial:
        nodes = [site.encounter.node]
    elif site.rooms:
        nodes = [room.node for room in site.rooms]
    elif site.encounter is not None:
        nodes = [site.encounter.node]
    else:
        nodes = []

    checks: dict[tuple[str, int], SiteCheckIntel] = {}
    for node in nodes:
        for check in _node_checks(node):
            checks.setdefault((check.stat, check.difficulty), check)

    return SiteIntel(
        checks=sorted(checks.values(), key=lambda check: (check.difficulty, check.stat)),
        # Negotiable means a full pass exists that fights nobody — a bloodless
        # option in one room does not excuse the raider pack in the next.
        negotiable=bool(nodes) and all(_room_bloodless(node) for node in nodes),
    )


def intel_phrase(intel: SiteIntel) -> str | None:
    """Short rumor text for the discovery bell, or None when nothing to hint."""
    if not intel.checks:
        return None
    stats = ", ".join(f"{check.stat.upper()} {check.difficulty}" for check in intel.checks[:3])
    if intel.negotiable:
        return f"Word is {stats} might settle it without a shot."
    return f"Word is the place favors {stats}."
