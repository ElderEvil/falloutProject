"""Pure bio rendering and seeded rumor selection over the bio catalog."""

from __future__ import annotations

import html
import random
from typing import TYPE_CHECKING

from app.core.enums import RaceEnum
from app.options.bios import (
    NEWBORN_BIO_TEMPLATES,
    NEWBORN_EVENTS,
    RACE_BARE_TEMPLATES,
    RACE_VISITED_TEMPLATES,
    ZONE_RUMORS,
)

if TYPE_CHECKING:
    from types import ModuleType


def _linked_parent_names(
    first_name: str,
    second_name: str,
    first_id: str,
    second_id: str,
    vault_id: str,
) -> tuple[str, str]:
    """Escape parent names and link their dossier pages."""
    max_name_len = 30
    safe_first_name = html.escape(first_name[:max_name_len])
    safe_second_name = html.escape(second_name[:max_name_len])
    first_link = f'<a href="/vault/{vault_id}/dwellers/{first_id}" class="dweller-link">{safe_first_name}</a>'
    second_link = f'<a href="/vault/{vault_id}/dwellers/{second_id}" class="dweller-link">{safe_second_name}</a>'
    return first_link, second_link


def render_newborn_bio(
    mother_name: str,
    father_name: str,
    mother_id: str,
    father_id: str,
    vault_id: str,
) -> str:
    """Render a newborn's arrival bio, linking both parents."""
    template = random.choice(NEWBORN_BIO_TEMPLATES)
    event = random.choice(NEWBORN_EVENTS)
    mother_link, father_link = _linked_parent_names(mother_name, father_name, mother_id, father_id, vault_id)
    return template.format(mother=mother_link, father=father_link, event=event)


def render_adopted_child_bio(
    first_parent_name: str,
    second_parent_name: str,
    first_parent_id: str,
    second_parent_id: str,
    vault_id: str,
) -> str:
    """Render a seeded child's adoptive arrival without a biological birth claim."""
    first_link, second_link = _linked_parent_names(
        first_parent_name, second_parent_name, first_parent_id, second_parent_id, vault_id
    )
    return f"I was adopted by {first_link} and {second_link} when I came to the vault."


def _join_visited(visited: list[str]) -> str:
    if len(visited) > 1:
        return f"{', '.join(visited[:-1])}, and {visited[-1]}"
    return visited[0] if visited else ""


def _human_bio(origin: str, visited: list[str]) -> str:
    if not visited:
        return f"Born in {origin}. Before the vault, I wandered the wastes alone."
    return f"Born in {origin}. Before the vault, I wandered through {_join_visited(visited)}."


def render_bio(
    origin: str,
    visited: list[str],
    *,
    race: RaceEnum | None,
    rng: random.Random | ModuleType = random,
) -> str:
    """Render a first-person backstory bio for an origin, visited places, and race."""
    if race is None or race == RaceEnum.HUMAN:
        return _human_bio(origin, visited)
    if not visited:
        return RACE_BARE_TEMPLATES[race].format(origin=origin)
    pool = RACE_VISITED_TEMPLATES[race]
    template = rng.choice(pool) if len(pool) > 1 else pool[0]
    return template.format(origin=origin, visited=_join_visited(visited))


def maybe_zone_rumor(rng: random.Random | ModuleType, chance: float) -> str | None:
    """Return one unresolved wasteland rumour, or None when the chance roll misses."""
    if chance <= 0 or rng.random() >= chance:
        return None
    return rng.choice(ZONE_RUMORS)
