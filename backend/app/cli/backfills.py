"""CLI commands for retroactive backfills.

Thin wrappers over the service layer per AGENTS.md.

Usage (from backend/):
    uv run fo-cli backfill-bio-places --vault <UUID>
    uv run fo-cli backfill-bio-places --all-active --max-dwellers 50 --max-vaults 10
    uv run fo-cli backfill-unlock-discoveries --vault <UUID>
    uv run fo-cli backfill-unlock-discoveries --all-active
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated
from uuid import UUID

import typer

from app import crud
from app.db.session import async_session_maker
from app.services.bio_place_backfill_service import bio_place_backfill_service
from app.services.discovery_backfill_service import discovery_backfill_service
from app.services.quest_state_objective_backfill_service import quest_state_objective_backfill_service
from app.utils.exceptions import ResourceNotFoundException

app = typer.Typer(
    name="backfill",
    help="Retroactive backfill commands for bios, places, and discovery unlocks.",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


@app.command(name="backfill-state-objectives")
def backfill_state_objectives() -> None:
    """Convert legacy timed state objectives to immediate claimable objectives."""

    async def _run() -> int:
        async with async_session_maker() as session:
            return await quest_state_objective_backfill_service.backfill_started_state_objectives(session)

    fixed = asyncio.run(_run())
    typer.echo(f"Backfill complete: {fixed} state objective(s) repaired.")


@app.command(name="backfill-bio-places")
def backfill_bio_places(
    vault: Annotated[
        str | None,
        typer.Option(help="Vault UUID to limit scope; ignored when --all-active is set"),
    ] = None,
    max_dwellers: Annotated[
        int,
        typer.Option(help="Maximum dwellers to process per vault"),
    ] = 100,
    all_active: Annotated[
        bool,
        typer.Option(help="Process all active (non-deleted) vaults"),
    ] = False,
    max_vaults: Annotated[
        int,
        typer.Option(help="Maximum active vaults to process"),
    ] = 100,
) -> None:
    """Extract origin/visited places from dweller bios and register them on the world map."""
    if vault and not all_active:
        try:
            UUID(vault)
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid vault UUID: {vault!r}") from exc

    async def _run() -> int | dict[UUID, int]:
        if not vault and not all_active:
            raise ValueError("Either --vault or --all-active must be provided")

        async with async_session_maker() as session:
            if all_active:
                return await bio_place_backfill_service.backfill_bio_places_for_active_vaults(
                    session,
                    max_dwellers_per_vault=max_dwellers,
                    max_vaults=max_vaults,
                )

            try:
                vault_obj = await crud.vault.get(session, UUID(vault))
            except ResourceNotFoundException as exc:
                raise ValueError(f"Vault {vault} not found") from exc

            return await bio_place_backfill_service.backfill_bio_places_for_vault(
                session,
                vault_obj.id,
                max_dwellers=max_dwellers,
            )

    try:
        result = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"Backfill failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if isinstance(result, dict):
        total = sum(result.values())
        typer.echo(f"Backfill complete: {total} dweller bio places registered across {len(result)} vaults.")
        for vault_id, count in sorted(result.items()):
            typer.echo(f"  {vault_id}: {count}")
    else:
        typer.echo(f"Backfill complete: {result} dweller bio places registered.")


@app.command(name="backfill-unlock-discoveries")
def backfill_unlock_discoveries(
    vault: Annotated[
        str | None,
        typer.Option(help="Vault UUID to limit scope; ignored when --all-active is set"),
    ] = None,
    all_active: Annotated[
        bool,
        typer.Option(help="Process all non-deleted vaults"),
    ] = False,
    max_vaults: Annotated[
        int,
        typer.Option(help="Maximum active vaults to process"),
    ] = 100,
) -> None:
    """Link DISCOVERY locations to their finding dweller and mark them unlocked."""
    if vault and not all_active:
        try:
            UUID(vault)
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid vault UUID: {vault!r}") from exc

    async def _run() -> int | dict[UUID, int]:
        if not vault and not all_active:
            raise ValueError("Either --vault or --all-active must be provided")

        async with async_session_maker() as session:
            if all_active:
                return await discovery_backfill_service.unlock_discoveries_for_active_vaults(
                    session,
                    max_vaults=max_vaults,
                )

            try:
                vault_obj = await crud.vault.get(session, UUID(vault))
            except ResourceNotFoundException as exc:
                raise ValueError(f"Vault {vault} not found") from exc

            return await discovery_backfill_service.unlock_discoveries_for_vault(session, vault_obj.id)

    try:
        result = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"Backfill failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if isinstance(result, dict):
        total = sum(result.values())
        typer.echo(f"Backfill complete: {total} discovery location(s) unlocked across {len(result)} vaults.")
        for vault_id, count in sorted(result.items()):
            typer.echo(f"  {vault_id}: {count}")
    else:
        typer.echo(f"Backfill complete: {result} discovery location(s) unlocked.")


if __name__ == "__main__":
    app()
