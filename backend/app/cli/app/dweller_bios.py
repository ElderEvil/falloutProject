"""CLI command: dweller-bios — fill missing bios for existing dwellers in a vault.

Thin wrapper over :class:`app.services.pregen_service.PregenService`; all
business logic (bio composition, map registration) lives in the service layer
per AGENTS.md.

Usage:
    uv run fo-cli dweller-bios --vault-id <UUID> [--count 5] [--seed 42] [--origin "Megaton"] [--force]
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import typer
from pydantic import UUID4

from app.crud.wasteland_location import wasteland_location
from app.services.pregen_service import pregen_service
from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)


def dweller_bios(
    vault_id: Annotated[UUID4, typer.Option("--vault-id", help="Target vault UUID")],
    count: Annotated[
        int,
        typer.Option("--count", "-c", min=0, help="Dwellers to fill (0 = all eligible)"),
    ] = 0,
    seed: Annotated[int | None, typer.Option("--seed", "-s", help="Deterministic RNG seed")] = None,
    origin: Annotated[str | None, typer.Option("--origin", "-o", help="Override origin for all dwellers")] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite bios even for dwellers that already have one"),
    ] = False,
) -> None:
    """Fill missing bios for existing dwellers in a vault.

    Each dweller without a bio gets a cheap template-based bio that mentions
    an origin settlement and 0-3 visited places.  Place names are drawn from
    the exploration discovery-name pools and registered on the world map so the
    frontend bio-linkify feature lights up immediately.

    Intended for dev/QA seeding — no LLM calls, no quota consumption, cheap.
    """

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            try:
                results = await pregen_service.fill_missing_bios(
                    db_session=session,
                    vault_id=vault_id,
                    count=count,
                    seed=seed,
                    origin=origin,
                    force=force,
                )
            except ResourceNotFoundException:
                typer.echo(f"Error: Vault not found (id={vault_id})", err=True)
                raise typer.Exit(code=1) from None

            if not results:
                typer.echo("No dwellers need a bio (use --force to overwrite existing ones).")
                return

            for i, result in enumerate(results, start=1):
                typer.echo(
                    f"  [{i}/{len(results)}] {result.first_name} {result.last_name or ''} "
                    f"| origin: {result.origin_place} | visited: {result.visited_count} "
                    f"| bio: {result.bio_length} chars"
                )

            map_locations = await wasteland_location.get_by_vault(session, vault_id)
            typer.echo(f"\n✓ Updated bios for {len(results)} dwellers in vault {vault_id}")
            typer.echo(f"  Total map locations in vault: {len(map_locations)}")

    try:
        asyncio.run(_run())
        typer.echo("✓ dweller-bios complete.")
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("dweller-bios failed")
        typer.echo("Error: dweller-bios failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc
