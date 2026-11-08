"""CLI commands: pregen-dwellers and dweller-bios — dev/QA bio + map seeding.

Thin wrappers over :class:`app.services.pregen_service.PregenService`; all
business logic (dweller creation, bio composition, map registration) lives in
the service layer per AGENTS.md.

Usage:
    uv run fo-cli pregen-dwellers --vault-id <UUID> [--count 5] [--seed 42] [--origin "Megaton"]
    uv run fo-cli dweller-bios --vault-id <UUID> [--count 5] [--seed 42] [--origin "Megaton"] [--force]
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

import typer

from app.crud.world_location import world_location
from app.services.pregen_service import pregen_service
from app.utils.exceptions import ResourceNotFoundException

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.services.pregen_service import PregenResult

logger = logging.getLogger(__name__)

SessionRunner = Callable[["AsyncSession"], Awaitable[list["PregenResult"]]]


async def _run_pregen(
    vault_id: UUID,
    run: SessionRunner,
    headline: str,
    empty_hint: str | None = None,
) -> None:
    from app.db.session import async_session_maker

    async with async_session_maker() as session:
        try:
            results = await run(session)
        except ResourceNotFoundException:
            typer.echo(f"Error: Vault not found (id={vault_id})", err=True)
            raise typer.Exit(code=1) from None

        if not results and empty_hint:
            typer.echo(empty_hint)
            return

        for i, result in enumerate(results, start=1):
            typer.echo(
                f"  [{i}/{len(results)}] {result.first_name} {result.last_name or ''} "
                f"| origin: {result.origin_place} | visited: {result.visited_count} "
                f"| bio: {result.bio_length} chars"
            )

        map_locations = await world_location.get_states_by_vault(session, vault_id)
        typer.echo(headline.format(count=len(results)))
        typer.echo(f"  Total map locations in vault: {len(map_locations)}")


def _execute(command: str, run: Callable[[], Coroutine[Any, Any, None]]) -> None:
    try:
        asyncio.run(run())
        typer.echo(f"✓ {command} complete.")
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("%s failed", command)
        typer.echo(f"Error: {command} failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc


def pregen_dwellers(
    vault_id: Annotated[UUID, typer.Option("--vault-id", help="Target vault UUID")],
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
        await _run_pregen(
            vault_id,
            lambda session: pregen_service.pregen_dwellers(
                db_session=session,
                vault_id=vault_id,
                count=count,
                seed=seed,
                origin=origin,
            ),
            headline=f"\n✓ Created {{count}} dwellers in vault {vault_id}",
        )

    _execute("pregen-dwellers", _run)


def dweller_bios(
    vault_id: Annotated[UUID, typer.Option("--vault-id", help="Target vault UUID")],
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
        await _run_pregen(
            vault_id,
            lambda session: pregen_service.fill_missing_bios(
                db_session=session,
                vault_id=vault_id,
                count=count,
                seed=seed,
                origin=origin,
                force=force,
            ),
            headline=f"\n✓ Updated bios for {{count}} dwellers in vault {vault_id}",
            empty_hint="No dwellers need a bio (use --force to overwrite existing ones).",
        )

    _execute("dweller-bios", _run)
