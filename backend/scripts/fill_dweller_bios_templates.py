"""Fill dweller bios with template-generated backstories and map locations.

Run locally against a single vault:
    cd backend
    uv run python scripts/fill_dweller_bios_templates.py --vault <uuid> --max-to-fill 10
    uv run python scripts/fill_dweller_bios_templates.py --help

Requires ASYNC_DATABASE_URI in backend/.env (no LLM needed).
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Annotated
from uuid import UUID

import typer

from app import crud
from app.core.game_config import game_config
from app.db.session import async_session_maker
from app.models.dweller import Dweller
from app.services.map_service import map_service

logger = logging.getLogger(__name__)

VAULT_ID = "f7a4d013-6252-4c19-b2ba-0bd499fe6133"
MAX_TO_FILL = 10  # safety limit — adjust or remove
SKIP_DEAD = True
FORCE_REGENERATE = False  # set True to overwrite existing bios + re-register places

_ORIGIN_PLACES: list[str] = [
    "Megaton",
    "Diamond City",
    "Goodneighbor",
    "Sanctuary Hills",
    "Novac",
    "Primm",
    "Rivet City",
    "Tenpenny Tower",
    "Graygarden",
    "Covenant",
    "Oberland Station",
    "Somerville Place",
    "County Crossing",
    "The Slog",
    "Jamaica Plain",
    "Concord",
    "Lexington",
    "Quincy",
    "Cambridge",
    "Nuka-World",
]

_VISITED_PLACES: list[str] = [
    "the Capital Wasteland",
    "the Mojave desert",
    "the Glowing Sea",
    "the Commonwealth",
    "Appalachia",
    "Far Harbor",
    "Point Lookout",
    "the Pitt",
    "Zion Canyon",
    "Big MT",
    "the Divide",
    "Vault-Tec HQ",
    "Red Rocket",
    "Starlight Drive-In",
    "Museum of Freedom",
    "Bunker Hill",
    "Mass Pike Tunnel",
    "Fort Hagen",
    "Poseidon Energy",
]

_STAT_NAMES = [
    ("strength", "Strength"),
    ("perception", "Perception"),
    ("endurance", "Endurance"),
    ("charisma", "Charisma"),
    ("intelligence", "Intelligence"),
    ("agility", "Agility"),
    ("luck", "Luck"),
]

_TEMPLATES: dict[str, list[str]] = {
    "strength": [
        (
            "Originally from {origin}, {name} never met a crate they couldn't lift or a door "
            "they couldn't force. With Strength {strength}, they keep the vault's heavy work running "
            "— and still tell stories about {visited}."
        ),
        (
            "Born in {origin} and raised on a diet of protein rations and stubbornness, {name} "
            "backs up every argument with a {rarity} punch and a Strength of {strength}. "
            "They still carry a memento from {visited}."
        ),
    ],
    "perception": [
        (
            "{name} came to the vault from {origin}, where they learned to notice things others miss: "
            "a flicker in the lights, a whisper in the vents, a radroach before it rounds the corner. "
            "Perception {perception} keeps the vault watchful, and they never forget {visited}."
        ),
        (
            "Eyes like a hawk and patience like a sniper, {name} left {origin} to read rooms before "
            "entering them. Perception {perception} makes them the vault's early warning system — "
            "a skill honed in {visited}."
        ),
    ],
    "endurance": [
        (
            "While others from {origin} complain about reactor heat and double shifts, {name} just "
            "keeps going. Endurance {endurance} and a {rarity} constitution make them the vault's rock, "
            "though {visited} tested even their limits."
        ),
        (
            "{name} has survived leaks, outages, and one memorable radscorpion incident with barely a cough. "
            "Endurance {endurance} isn't a stat — it's a lifestyle they picked up in {origin} and refined in {visited}."
        ),
    ],
    "charisma": [
        (
            "{name} could talk a raider into a hug and a robot into a joke. Hailing from {origin}, "
            "their Charisma {charisma} keeps morale high and arguments short, no matter how tense "
            "things get after a run to {visited}."
        ),
        (
            "Every room brightens when {name} walks in. Charisma {charisma} and a {rarity} smile make them "
            "the vault's unofficial ambassador — a reputation that followed them from {origin} to {visited}."
        ),
    ],
    "intelligence": [
        (
            "{name} reads manuals for fun and fixes things that weren't technically broken. Originally from {origin}, "
            "Intelligence {intelligence} keeps the vault's tech one step ahead of the wasteland, "
            "even if {visited} still has them stumped."
        ),
        (
            "Ask {name} how the water chip works and settle in for a very detailed answer. "
            "Their Intelligence {intelligence} makes them the vault's living encyclopedia, "
            "with footnotes gathered in {origin} and cross-referenced in {visited}."
        ),
    ],
    "agility": [
        (
            "Quick hands, quick feet, and a habit of being somewhere else before trouble arrives — "
            "{name} relies on Agility {agility} to stay one step ahead. They learned that lesson in {origin} "
            "and put it to use scavenging {visited}."
        ),
        (
            "{name} moves like they were born in the vents. Agility {agility} makes them the first pick for any "
            "{status} job that needs speed, a talent that kept them alive in both {origin} and {visited}."
        ),
    ],
    "luck": [
        (
            "{name} once found a pre-War snack cake in a ruined locker and considered it normal. "
            "Luck {luck} follows them like a loyal pet from {origin} straight through {visited}."
        ),
        (
            "Cards, dice, or surviving a molerat ambush — {name} always seems to land on their feet. "
            "Luck {luck} and a {rarity} streak kept them interesting in {origin} and got them "
            "out of {visited} in one piece."
        ),
    ],
}


def _highest_stat(dweller: Dweller) -> str:
    """Return the lowercase name of the highest SPECIAL stat, breaking ties randomly."""
    values = [(key, getattr(dweller, key, 1)) for key, _ in _STAT_NAMES]
    max_value = max(value for _, value in values)
    top = [key for key, value in values if value == max_value]
    return random.choice(top)


def _pick_places(dweller: Dweller) -> tuple[str, list[str]]:
    """Return an origin place and rarity-scaled visited places for a dweller."""
    # Seed per dweller so the same dweller always gets the same places if rerun.
    rng = random.Random(str(dweller.id))
    origin = rng.choice(_ORIGIN_PLACES)
    desired = game_config.bio.max_visited(dweller.rarity.value)
    visited_count = min(desired, len(_VISITED_PLACES))
    visited = rng.sample(_VISITED_PLACES, k=visited_count)
    return origin, visited


def _join_places(places: list[str]) -> str:
    """Join place names with natural English list formatting (Oxford comma for 3+)."""
    if len(places) == 1:
        return places[0]
    if len(places) == 2:
        return f"{places[0]} and {places[1]}"
    *rest, last = places
    return f"{', '.join(rest)}, and {last}"


def _build_bio(dweller: Dweller, origin: str, visited: list[str]) -> str:
    stat_key = _highest_stat(dweller)
    template = random.choice(_TEMPLATES[stat_key])
    last = dweller.last_name or ""
    full_name = f"{dweller.first_name} {last}".strip()

    return template.format(
        name=full_name,
        first_name=dweller.first_name,
        last_name=last,
        rarity=dweller.rarity.value,
        status=dweller.status.value,
        age_group=dweller.age_group.value,
        level=dweller.level,
        strength=dweller.strength,
        perception=dweller.perception,
        endurance=dweller.endurance,
        charisma=dweller.charisma,
        intelligence=dweller.intelligence,
        agility=dweller.agility,
        luck=dweller.luck,
        origin=origin,
        visited=_join_places(visited),
    )


async def main(
    vault_id: str = VAULT_ID,
    max_to_fill: int = MAX_TO_FILL,
    skip_dead: bool = SKIP_DEAD,
    force_regenerate: bool = FORCE_REGENERATE,
) -> None:
    filled = 0
    async with async_session_maker() as session:
        vault = await crud.vault.get(session, UUID(vault_id))
        if vault is None:
            print(f"Vault {vault_id} not found")
            return

        dwellers = await crud.dweller.get_multi_by_vault(session, vault.id, limit=1000)
        candidates = [d for d in dwellers if (force_regenerate or not d.bio) and (not skip_dead or not d.is_dead)]
        if max_to_fill:
            candidates = candidates[:max_to_fill]

        for dweller in candidates:
            try:
                origin, visited = _pick_places(dweller)
                bio = _build_bio(dweller, origin, visited)
                dweller.bio = bio
                session.add(dweller)
                await map_service.register_bio_places(
                    session,
                    dweller,
                    origin_place=origin,
                    visited_places=visited,
                )
                filled += 1
                print(f"[{filled}] {dweller.first_name}: {bio[:80]}...")
            except Exception:
                logger.exception("Failed to fill bio for dweller %s", dweller.id)

        await session.commit()

    print(f"Filled {filled} bios for vault {vault_id}")


app = typer.Typer(help="Fill dweller bios with template-generated backstories and map locations.")


@app.command()
def fill(
    vault: Annotated[str, typer.Option(help="Vault UUID")] = VAULT_ID,
    max_to_fill: Annotated[int, typer.Option(help="Max dwellers to fill (0 = unlimited)")] = MAX_TO_FILL,
    skip_dead: Annotated[bool, typer.Option(help="Skip dead dwellers")] = SKIP_DEAD,
    force_regenerate: Annotated[
        bool, typer.Option(help="Overwrite existing bios and re-register places")
    ] = FORCE_REGENERATE,
) -> None:
    """Fill dweller bios with template-generated backstories and map locations."""
    try:
        UUID(vault)
    except ValueError:
        raise typer.BadParameter(f"Invalid vault UUID: {vault!r}") from None
    asyncio.run(main(vault_id=vault, max_to_fill=max_to_fill, skip_dead=skip_dead, force_regenerate=force_regenerate))


def main_cli() -> None:
    app()


if __name__ == "__main__":
    main_cli()
