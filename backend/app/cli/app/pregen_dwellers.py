"""CLI command: pregen-dwellers — deterministic bio + map seeding for dev/QA.

Thin wrapper over :class:`app.services.pregen_service.PregenService`; all
business logic (dweller creation, bio composition, map registration) lives in
the service layer per AGENTS.md.

Usage:
    uv run fo-cli pregen-dwellers --vault-id <UUID> [--count 5] [--seed 42] [--origin "Megaton"]
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


def pregen_dwellers(
    vault_id: Annotated[UUID4, typer.Option("--vault-id", help="Target vault UUID")],
    count: Annotated[int, typer.Option("--count", "-c", min=1, max=50, help="Dwellers to generate (1-50)")] = 5,
    seed: Annotated[int | None, typer.Option("--seed", "-s", help="Deterministic RNG seed")] = None,
    origin: Annotated[str | None, typer.Option("--origin", "-o", help="Override origin for all dwellers")] = None,
) -> None:
    """Pre-generate dwellers with deterministic bios and world-map place markers.

    Each dweller gets a cheap template-based bio that mentions an origin
    settlement and 0-3 visited places.  Place names are drawn from the
    exploration discovery-name pools and registered on the world map so the
    frontend bio-linkify feature lights up immediately.

    Intended for dev/QA seeding — no LLM calls, no quota consumption, cheap.
    """

    async def _run() -> None:
        from app.cli.main import _make_async_session

        session_factory = _make_async_session()

        async with session_factory() as session:
            try:
                results = await pregen_service.pregen_dwellers(
                    db_session=session,
                    vault_id=vault_id,
                    count=count,
                    seed=seed,
                    origin=origin,
                )
            except ResourceNotFoundException:
                typer.echo(f"Error: Vault not found (id={vault_id})", err=True)
                raise typer.Exit(code=1) from None

            for i, result in enumerate(results, start=1):
                typer.echo(
                    f"  [{i}/{len(results)}] {result.first_name} {result.last_name or ''} "
                    f"| origin: {result.origin_place} | visited: {result.visited_count} "
                    f"| bio: {result.bio_length} chars"
                )

            map_locations = await wasteland_location.get_by_vault(session, vault_id)
            typer.echo(f"\n✓ Created {len(results)} dwellers in vault {vault_id}")
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
