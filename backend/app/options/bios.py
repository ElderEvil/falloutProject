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


# Secondhand, unresolved claims about the Quiet Zone and its "anomalies": never
# confirmed, always deniable. Appended to a small share of generated bios.
ZONE_RUMORS: tuple[str, ...] = (
    (
        "I've heard the scavengers talk about the Quiet Zone, a fenced industrial site where the air "
        "supposedly bends after a radstorm. The engineers say the scavengers drink too much."
    ),
    "I carry a pouch of rusty bolts for testing bad ground. I've never needed them, which proves nothing.",
    (
        "A scout I knew swore she saw a fireball hovering over the Quiet Zone. Her old caravan partner "
        "says it was a gas leak and three bottles of vodka."
    ),
    "I keep a map with one spot crossed out and rewritten: DON'T GO BACK. Nobody will tell me what's there.",
    (
        "They say some ruins near the old exclusion fence grow valuables the way forests grow mushrooms. "
        "I've only found scrap so far."
    ),
    (
        "A masked guide led me through a fence line once, then vanished before I could pay. The rest of "
        "the party says I imagined him."
    ),
    (
        "My detector clicks near radiation, loose wiring, and occasionally nothing at all. It's useless. "
        "I trust it anyway."
    ),
    (
        "My cousin sold a warm stone from past the perimeter for two hundred caps. His buyer argued about "
        "the price for three days."
    ),
)


def maybe_zone_rumor(rng: random.Random | ModuleType, chance: float) -> str | None:
    """Return one unresolved Quiet Zone rumour, or None when the chance roll misses."""
    if chance <= 0 or rng.random() >= chance:
        return None
    return rng.choice(ZONE_RUMORS)
