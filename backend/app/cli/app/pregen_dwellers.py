"""CLI command: pregen-dwellers — deterministic bio + map seeding for dev/QA.

Usage:
    uv run fo-cli pregen-dwellers --vault-id <UUID> [--count 5] [--seed 42] [--origin "Megaton"]
"""

from __future__ import annotations

import logging
import random as std_random
from typing import Annotated

import typer
from pydantic import UUID4

from app import crud
from app.schemas.dweller import DwellerUpdate
from app.services.exploration.data_loader import load_discovery_names
from app.services.map_service import map_service
from app.utils.places import GENERIC_ORIGIN_SKIP, normalize_place_name

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# bio templates — cheap, deterministic, NO LLM
# ------------------------------------------------------------------

ADULT_BIO_TEMPLATES: list[str] = [
    "Grew up in {origin}. {first_name} spent years wandering the wastes{visited_str} before finding this vault.",
    "Originally from {origin}, {first_name} roamed{visited_str} seeking shelter. The wasteland left its mark.",
    "A child of {origin}, {first_name} survived the trek{visited_str}. Every step was a lesson in endurance.",
    "{origin} native. {first_name} earned a reputation scavenging{visited_str} before joining the vault community.",
    "Born near {origin}, {first_name} travelled{visited_str} during the Great Storm. Survival was uncertain.",
    "Hails from the outskirts of {origin}. {first_name} passed through{visited_str} on the long road to safety.",
    "The ruins of {origin} were {first_name}'s first home. They explored{visited_str} before the vault took them in.",
    "A wanderer from {origin}. {first_name} traded stories with survivors{visited_str} along the way.",
]

MAX_PICK_ATTEMPTS = 50
NAME_MAX_LEN = 64


# ------------------------------------------------------------------
# pure helpers (testable, no I/O)
# ------------------------------------------------------------------


def _clean_name(name: str) -> str:
    """Strip whitespace and clamp to NAME_MAX_LEN characters."""
    return name.strip()[:NAME_MAX_LEN]


def _pick_place(
    rng: std_random.Random,
    prefixes: list[str],
    suffixes: list[str],
) -> str:
    """Pick a random prefix-suffix combo, avoiding GENERIC_ORIGIN_SKIP tokens."""
    for _ in range(MAX_PICK_ATTEMPTS):
        raw = f"{rng.choice(prefixes)} {rng.choice(suffixes)}"
        if normalize_place_name(raw) not in GENERIC_ORIGIN_SKIP:
            return _clean_name(raw)
    # Exhausted attempts — return a safe fallback
    return _clean_name(f"{rng.choice(prefixes)} {rng.choice(suffixes)}")


def _format_visited_str(places: list[str]) -> str:
    """Format a list of place names into a grammatically correct inline phrase.

    Returns an empty string for zero places, or a leading-", " phrase like
    ", passing through the Rusty Shack" or ", passing through Rusty Shack, Abandoned Depot, and Glowing Silo".
    """
    if not places:
        return ""
    joined = " and ".join(places) if len(places) <= 2 else ", ".join(places[:-1]) + ", and " + places[-1]
    return f", passing through {joined}"


def _compose_bio(
    rng: std_random.Random,
    first_name: str,
    origin: str,
    visited: list[str],
) -> str:
    """Pick a random template and render it with the dweller's origin + visited places."""
    template = rng.choice(ADULT_BIO_TEMPLATES)
    visited_str = _format_visited_str(visited)
    return template.format(first_name=first_name, origin=origin, visited_str=visited_str)


# ------------------------------------------------------------------
# main command
# ------------------------------------------------------------------


def pregen_dwellers(
    vault_id: Annotated[UUID4, typer.Option("--vault-id", help="Target vault UUID")],
    count: Annotated[
        int, typer.Option("--count", "-c", min=1, max=50, help="Dwellers to generate (1-50)")
    ] = 5,
    seed: Annotated[int | None, typer.Option("--seed", "-s", help="Deterministic RNG seed")] = None,
    origin: Annotated[
        str | None, typer.Option("--origin", "-o", help="Override origin for all dwellers")
    ] = None,
) -> None:
    """Pre-generate dwellers with deterministic bios and world-map place markers.

    Each dweller gets a cheap template-based bio that mentions an origin
    settlement and 0-3 visited places.  Place names are drawn from the
    exploration discovery-name pools and registered on the world map so the
    frontend bio-linkify feature lights up immediately.

    Intended for dev/QA seeding — no LLM calls, no quota consumption, cheap.
    """
    import asyncio

    rng = std_random.Random(seed)

    # Load name pools once
    name_pools = load_discovery_names()
    prefixes: list[str] = name_pools["prefixes"]
    suffixes: list[str] = name_pools["suffixes"]

    async def _run() -> None:
        from app.cli.main import _make_async_session

        session_factory = _make_async_session()

        async with session_factory() as session:
            # Validate vault exists
            from app.utils.exceptions import ResourceNotFoundException

            try:
                _ = await crud.vault.get(session, id=vault_id)
            except ResourceNotFoundException:
                typer.echo(f"Error: Vault not found (id={vault_id})", err=True)
                raise typer.Exit(code=1) from None

            created_ids: list[UUID4] = []

            for i in range(count):
                # 1. Create random dweller
                dweller = await crud.dweller.create_random(session, vault_id=vault_id)
                created_ids.append(dweller.id)

                # 2. Pick origin + visited places
                origin_place = _clean_name(origin) if origin else _pick_place(rng, prefixes, suffixes)
                visited_count = rng.randint(0, 3)
                visited_places = [_pick_place(rng, prefixes, suffixes) for _ in range(visited_count)]

                # 3. Compose bio
                bio = _compose_bio(rng, dweller.first_name, origin_place, visited_places)

                # 4. Update dweller bio
                await crud.dweller.update(session, id=dweller.id, obj_in=DwellerUpdate(bio=bio))

                # 5. Register map places
                await map_service.register_bio_places(
                    db_session=session,
                    dweller=dweller,
                    origin_place=origin_place,
                    visited_places=visited_places,
                    explicit_origin=origin,
                )

                typer.echo(
                    f"  [{i + 1}/{count}] {dweller.first_name} {dweller.last_name or ''} "
                    f"| origin: {origin_place} | visited: {visited_count} | bio: {len(bio)} chars"
                )

            # Summary
            from app.crud.wasteland_location import wasteland_location

            map_locations = await wasteland_location.get_by_vault(session, vault_id)
            typer.echo(f"\n✓ Created {len(created_ids)} dwellers in vault {vault_id}")
            typer.echo(f"  Total map locations in vault: {len(map_locations)}")

    try:
        asyncio.run(_run())
        typer.echo("✓ pregen-dwellers complete.")
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("pregen-dwellers failed")
        typer.echo("Error: pregen-dwellers failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc
