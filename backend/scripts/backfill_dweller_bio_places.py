"""Retro-active bio place backfill: extract origin/visited places from dweller bios
and register them on the world map via map_service.register_bio_places.

Usage:
    cd backend
    uv run python scripts/backfill_dweller_bio_places.py
    uv run python scripts/backfill_dweller_bio_places.py --vault <uuid>
    uv run python scripts/backfill_dweller_bio_places.py --vault <uuid> --max-dwellers <n>

Requires ASYNC_DATABASE_URI in backend/.env.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Annotated
from uuid import UUID

import typer
from sqlmodel import select

from app import crud
from app.db.session import async_session_maker
from app.models.dweller import Dweller
from app.models.wasteland_location import DwellerLocation
from app.services.map_service import map_service

logger = logging.getLogger(__name__)

VAULT_ID = "f7a4d013-6252-4c19-b2ba-0bd499fe6133"
MAX_DWELLERS = 100  # safety limit

# ---------------------------------------------------------------------------
# Known place lists — mirror the filler script's origin / visited places
# ---------------------------------------------------------------------------

_KNOWN_ORIGIN_PLACES: list[str] = [
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

_KNOWN_VISITED_PLACES: list[str] = [
    "the Capital Wasteland",
    "the Mojave desert",
    "the Glowing Sea",
    "the Commonwealth",
    "Appalachia",
    "Far Harbor",
    "Point Lookout",
    "the Pitt",
    " Zion Canyon",
    "Big MT",
    "the Divide",
    "Vault-Tec HQ",
    "Red Rocket",
    "Starlight Drive-In",
    "Sanctuary Hills",
    "Museum of Freedom",
    "Bunker Hill",
    "Mass Pike Tunnel",
    "Fort Hagen",
    "Poseidon Energy",
]

# ---------------------------------------------------------------------------
# Place extraction
# ---------------------------------------------------------------------------


def _build_origin_regex() -> re.Pattern[str]:
    """Build a compiled regex that matches any known origin place (case-insensitive, word-boundary)."""
    patterns = []
    for place in _KNOWN_ORIGIN_PLACES:
        patterns.append(r"\b" + re.escape(place) + r"\b")
    return re.compile("|".join(patterns), re.IGNORECASE)


def _build_visited_regex() -> re.Pattern[str]:
    """Build a compiled regex that matches any known visited place (case-insensitive, word-boundary).

    Visited places may have leading/trailing spaces in the list (e.g. " Zion Canyon");
    we strip them before building the regex so the pattern matches naturally in text.
    """
    patterns = []
    for place in _KNOWN_VISITED_PLACES:
        stripped = place.strip()
        patterns.append(r"\b" + re.escape(stripped) + r"\b")
    return re.compile("|".join(patterns), re.IGNORECASE)


_ORIGIN_RE = _build_origin_regex()
_VISITED_RE = _build_visited_regex()


def _extract_places_from_bio(bio: str | None) -> tuple[str | None, list[str]]:
    """Scan *bio* for known origin and visited place names.

    Returns (origin_place, visited_places):
    - *origin_place*: the first matched origin place (preserving original casing from the
      known origin list), or None.
    - *visited_places*: deduplicated list of visited place matches (preserving the trimmed
      canonical form from _KNOWN_VISITED_PLACES), excluding any place that was already
      picked as the origin.
    """
    if not bio:
        return None, []

    # --- origin scan ---
    origin_place: str | None = None
    origin_match = _ORIGIN_RE.search(bio)
    if origin_match:
        matched_text = origin_match.group(0)
        for place in _KNOWN_ORIGIN_PLACES:
            if place.lower() == matched_text.lower():
                origin_place = place
                break

    # --- visited scan ---
    visited_places: list[str] = []
    seen_normalized: set[str] = set()
    if origin_place:
        seen_normalized.add(origin_place.lower())

    for match in _VISITED_RE.finditer(bio):
        matched_text = match.group(0)
        normalized = matched_text.lower()
        if normalized in seen_normalized:
            continue
        for place in _KNOWN_VISITED_PLACES:
            if place.strip().lower() == normalized:
                visited_places.append(place.strip())
                seen_normalized.add(normalized)
                break

    return origin_place, visited_places


# ---------------------------------------------------------------------------
# Main backfill logic
# ---------------------------------------------------------------------------


async def main(vault_uuid: str | None = None, max_dwellers: int = MAX_DWELLERS) -> int:
    """Run the backfill for one vault.

    When *vault_uuid* is None, the project vault (VAULT_ID) is used.

    Returns the count of dwellers whose places were successfully registered.
    """
    effective_uuid = vault_uuid or VAULT_ID
    processed = 0

    async with async_session_maker() as session:
        vault = await crud.vault.get(session, UUID(effective_uuid))
        if vault is None:
            logger.warning("Vault %s not found", effective_uuid)
            return 0

        dwellers = await crud.dweller.get_multi_by_vault(session, vault.id, limit=max_dwellers)

        # Filter: has bio AND zero DwellerLocation rows
        candidates: list[Dweller] = []
        for d in dwellers:
            if not d.bio:
                continue
            # Check if the dweller has any existing DwellerLocation rows
            loc_count = await session.execute(
                select(DwellerLocation).where(DwellerLocation.dweller_id == d.id).limit(1)
            )
            if loc_count.first() is not None:
                continue  # already has locations -> skip
            candidates.append(d)
            if len(candidates) >= max_dwellers:
                break

        for dweller in candidates:
            try:
                origin, visited = _extract_places_from_bio(dweller.bio)
                if origin is None and not visited:
                    logger.debug("No known places in bio for dweller %s", dweller.id)
                    continue

                await map_service.register_bio_places(
                    session,
                    dweller,
                    origin_place=origin or "",
                    visited_places=visited,
                )
                processed += 1
                logger.info(
                    "Registered places for dweller %s (%s %s): origin=%s visited=%s",
                    dweller.id,
                    dweller.first_name,
                    dweller.last_name or "",
                    origin,
                    visited,
                )
            except Exception:
                logger.exception("Failed to register bio places for dweller %s", dweller.id)

        await session.commit()

    logger.info("Backfill complete: %d dwellers processed", processed)
    return processed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


app = typer.Typer(help="Backfill dweller bio places from bio text.")


@app.command()
def backfill(
    vault: Annotated[str, typer.Option(help="Vault UUID to limit scope")] = VAULT_ID,
    max_dwellers: Annotated[int, typer.Option(help="Maximum dwellers to process")] = MAX_DWELLERS,
) -> None:
    """Extract origin/visited places from dweller bios and register them on the world map."""
    count = asyncio.run(main(vault_uuid=vault, max_dwellers=max_dwellers))
    print(f"Backfill complete: {count} dweller bio places registered.")


def cli_entry() -> None:
    app()


if __name__ == "__main__":
    cli_entry()
