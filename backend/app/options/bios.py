"""Lore-safe pre-baked dweller bio templates, keyed by race.

The origin pool is shared across races, but each race frames it differently —
birthplace for humans, last-known site for ghouls and mutants, wake-site for
synths — so shared settlement names stay canon-safe for dwellers who were
never born there. Template origin/visited names must stay world-map
registrable (no "", "wasteland", "unknown").

Human rendering is deterministic by visited-count and byte-identical to the
legacy shapes; non-human races pick a variant through the caller's RNG so
seeded generation stays reproducible.
"""

from __future__ import annotations

import html
import random
from typing import TYPE_CHECKING

from app.options.races import RaceOption

if TYPE_CHECKING:
    from types import ModuleType

NEWBORN_BIO_TEMPLATES = (
    "Born during a {event}. {mother} and {father} couldn't be prouder.",
    "Arrived during {event}. The vault celebrates this new life.",
    "Entered the world during {event}. A blessing for {mother} and {father}.",
    "Born under {event}. {father} and {mother} welcome their bundle of joy.",
    "Came into existence during {event}. A new hope for the vault.",
    "Born during {event}. {mother} and {father} are overjoyed.",
    "First cry echoed through the vault during {event}. Precious to {mother} and {father}.",
    "Entered the shelter during {event}. {father} and {mother} celebrate.",
    "Born amidst {event}. A miracle for {mother} and {father}.",
    "Came from {mother} and {father} during {event}. The vault grows.",
)

NEWBORN_EVENTS = (
    "a quiet night",
    "a vault celebration",
    "a rad-storm",
    "an emergency drill",
    "a power outage",
    "the weekly ration distribution",
    "a radio broadcast",
    "the morning shift change",
    "a rare sunny day",
    "the lunch hour",
    "the night watch",
    "a calm afternoon",
    "the vault door sealing",
    "a happiness surge",
    "the quarterly inventory",
)


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
    max_name_len = 30
    safe_mother_name = html.escape(mother_name[:max_name_len])
    safe_father_name = html.escape(father_name[:max_name_len])
    mother_link = f'<a href="/vault/{vault_id}/dwellers/{mother_id}" class="dweller-link">{safe_mother_name}</a>'
    father_link = f'<a href="/vault/{vault_id}/dwellers/{father_id}" class="dweller-link">{safe_father_name}</a>'
    return template.format(mother=mother_link, father=father_link, event=event)


def _join_visited(visited: list[str]) -> str:
    if len(visited) > 1:
        return f"{', '.join(visited[:-1])}, and {visited[-1]}"
    return visited[0] if visited else ""


def _human_bio(origin: str, visited: list[str]) -> str:
    if not visited:
        return f"Born in {origin}. Before the vault, I wandered the wastes alone."
    return f"Born in {origin}. Before the vault, I wandered through {_join_visited(visited)}."


_RACE_VISITED_TEMPLATES: dict[RaceOption, tuple[str, ...]] = {
    RaceOption.GHOUL: (
        "I was someone else, somewhere else, before the bombs fell. The vault found me near {origin} — I'd come through {visited}.",
    ),
    RaceOption.SYNTH: ("I was not born. I woke up in a lab under {origin}, and I ran. {visited} saw me pass.",),
    RaceOption.SUPER_MUTANT: (
        "I was human once. The vats took that, and most of my memories with it. Last I knew: {origin}. Before that, {visited}.",
    ),
}

_RACE_BARE_TEMPLATES: dict[RaceOption, str] = {
    RaceOption.GHOUL: "I was someone else, somewhere else, before the bombs fell. The vault found me near {origin}. I'd stopped counting the years long before that.",
    RaceOption.SYNTH: "I was not born. I woke up in a lab under {origin}, and I ran. I haven't stopped since.",
    RaceOption.SUPER_MUTANT: "I was human once. The vats took that, and most of my memories with it. Last I knew: {origin}.",
}


def render_bio(
    origin: str,
    visited: list[str],
    *,
    race: RaceOption | None,
    rng: random.Random | ModuleType = random,
) -> str:
    """Render a first-person backstory bio for an origin, visited places, and race."""
    if race is None or race == RaceOption.HUMAN:
        return _human_bio(origin, visited)
    if not visited:
        return _RACE_BARE_TEMPLATES[race].format(origin=origin)
    pool = _RACE_VISITED_TEMPLATES[race]
    template = rng.choice(pool) if len(pool) > 1 else pool[0]
    return template.format(origin=origin, visited=_join_visited(visited))
