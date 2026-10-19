"""Curated parent links between named dweller templates.

Template JSON cannot carry family links, so the relationship is reconciled when
either side is created. The child's bio gets the same ``dweller-link`` anchor
used by generated family bios, which the biography renderer already sanitizes.
"""

import html
from dataclasses import dataclass

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_data import get_static_game_data
from app.models.dweller import Dweller
from app.schemas.dweller import DwellerTemplate


@dataclass(frozen=True)
class KnownParentLink:
    """A curated child -> parent template link and the names to anchor in the child bio."""

    child_template_id: str
    parent_template_id: str
    parent_bio_aliases: tuple[str, ...]


KNOWN_PARENT_LINKS: tuple[KnownParentLink, ...] = (
    KnownParentLink(
        child_template_id="lucy-maclean",
        parent_template_id="hank",
        parent_bio_aliases=("Hank",),
    ),
    KnownParentLink(
        child_template_id="sarah-lyons",
        parent_template_id="elder-lyons",
        parent_bio_aliases=("Elder Owyn Lyons", "Owyn Lyons"),
    ),
)


def _rarity_value(value: object) -> str:
    return str(getattr(value, "value", value)).lower()


def _matches_template(dweller: Dweller, template: DwellerTemplate) -> bool:
    return (
        not dweller.is_deleted
        and dweller.first_name == template.first_name
        and (dweller.last_name or None) == (template.last_name or None)
        and _rarity_value(dweller.rarity) == _rarity_value(template.rarity)
    )


def _find_dweller(dwellers: list[Dweller], template: DwellerTemplate) -> Dweller | None:
    matches = sorted(
        (dweller for dweller in dwellers if _matches_template(dweller, template)),
        key=lambda dweller: (dweller.created_at, str(dweller.id)),
    )
    return matches[0] if matches else None


def _linked_bio(text: str | None, parent: Dweller, aliases: tuple[str, ...], vault_id: UUID4) -> str | None:
    if not text:
        return text
    href = f"/vault/{vault_id}/dwellers/{parent.id}"
    if href in text:
        return text
    for alias in sorted(aliases, key=len, reverse=True):
        if alias in text:
            anchor = f'<a href="{href}" class="dweller-link">{html.escape(alias)}</a>'
            return text.replace(alias, anchor, 1)
    return text


def _link_bio_entries(child: Dweller, parent: Dweller, aliases: tuple[str, ...], vault_id: UUID4) -> bool:
    changed = False
    linked_bio = _linked_bio(child.bio, parent, aliases, vault_id)
    if linked_bio != child.bio:
        child.bio = linked_bio
        changed = True

    entries: list[dict] = []
    for entry in child.bio_entries or []:
        next_entry = dict(entry)
        linked_text = _linked_bio(str(entry.get("text") or ""), parent, aliases, vault_id)
        if linked_text != entry.get("text"):
            next_entry["text"] = linked_text
            changed = True
        entries.append(next_entry)
    if changed:
        child.bio_entries = entries
    return changed


async def reconcile_known_parent_links(
    db_session: AsyncSession,
    vault_id: UUID4,
    template_id: str,
) -> None:
    """Link Lucy/Hank or Sarah/Elder Lyons when both templates are in one vault."""
    relevant = [link for link in KNOWN_PARENT_LINKS if template_id in (link.child_template_id, link.parent_template_id)]
    if not relevant:
        return

    game_data = await get_static_game_data()
    dwellers = list(await crud.dweller.get_all_in_vault(db_session, vault_id))
    changed = False

    for link in relevant:
        child_template = game_data.get_dweller(link.child_template_id)
        parent_template = game_data.get_dweller(link.parent_template_id)
        if child_template is None or parent_template is None:
            continue

        child = _find_dweller(dwellers, child_template)
        parent = _find_dweller(dwellers, parent_template)
        if child is None or parent is None or child.id == parent.id:
            continue

        if child.parent_1_id is None:
            child.parent_1_id = parent.id
            db_session.add(child)
            changed = True

        if _link_bio_entries(child, parent, link.parent_bio_aliases, vault_id):
            db_session.add(child)
            changed = True

    if changed:
        await db_session.commit()
