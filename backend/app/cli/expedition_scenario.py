"""CLI command group: expedition-scenario — interactive expedition-site test setup."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated
from uuid import UUID

import typer

from app.core.config import settings
from app.services.exploration.expedition_scenario_service import expedition_scenario_service
from app.utils.exceptions import ResourceNotFoundException

app = typer.Typer(
    name="expedition-scenario",
    help="Dev/QA: build a playable interactive expedition-site scenario.",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


def _print_setup(result) -> None:
    typer.echo("Vault:")
    typer.echo(f"  id: {result.vault.id}")
    typer.echo(f"  created: {'yes (boosted)' if result.created_vault else 'no (existing)'}")
    typer.echo("Dweller:")
    typer.echo(f"  {result.dweller.display_name} (level {result.dweller.level}, id {result.dweller.id})")
    typer.echo("Exploration:")
    typer.echo(f"  id: {result.exploration.id}")
    typer.echo(f"  status: {result.exploration.status.value}")
    typer.echo("Available sites:")
    if result.available_sites:
        for site in result.available_sites:
            typer.echo(f"  - {site.id} ({site.name}, min level {site.min_dweller_level})")
    else:
        typer.echo("  (none)")
    if result.precleared_site_id:
        typer.echo(f"Pre-cleared site (hidden by 7-day anti-farm): {result.precleared_site_id}")
    typer.echo(f"Frontend: http://localhost:5173/vault/{result.vault.id}/exploration/{result.exploration.id}")
    login_email = result.owner_email or settings.FIRST_SUPERUSER_EMAIL
    typer.echo(f"Login: {login_email} (superuser — use the FIRST_SUPERUSER_PASSWORD from your .env)")


@app.command()
def setup(
    vault_id: Annotated[
        UUID | None,
        typer.Option("--vault-id", help="Target vault UUID (default: create a new boosted vault)"),
    ] = None,
    user_email: Annotated[
        str | None,
        typer.Option("--user-email", help="Owner email for a new vault (default: FIRST_SUPERUSER_EMAIL)"),
    ] = None,
    dweller_level: Annotated[int, typer.Option("--dweller-level", help="Level for the scenario dweller")] = 5,
    duration_hours: Annotated[int, typer.Option("--duration-hours", help="Exploration duration in hours (1-24)")] = 8,
    preclear: Annotated[
        str | None,
        typer.Option("--preclear", help="Site id to pre-clear (demonstrates the 7-day anti-farm lock)"),
    ] = None,
    special: Annotated[
        int,
        typer.Option(
            "--special",
            help="Every SPECIAL stat for the dweller (1-10). 5 keeps checks differentiated; 1 for defeat/death.",
        ),
    ] = 5,
) -> None:
    """Create a vault with one dweller on an active exploration and a populated site picker."""

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            result = await expedition_scenario_service.setup(
                session,
                vault_id=vault_id,
                user_email=user_email,
                dweller_level=dweller_level,
                duration_hours=duration_hours,
                preclear_site_id=preclear,
                special=special,
            )
            _print_setup(result)

    try:
        asyncio.run(_run())
        typer.echo("✓ expedition-scenario setup complete.")
    except (ResourceNotFoundException, ValueError) as exc:
        detail = exc.detail if isinstance(exc, ResourceNotFoundException) else str(exc)
        typer.echo(f"Error: {detail}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        logger.exception("expedition-scenario setup failed")
        typer.echo("Error: expedition-scenario setup failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def status(
    vault_id: Annotated[UUID, typer.Option("--vault-id", help="Target vault UUID")],
) -> None:
    """Print the vault's in-progress explorations and their site pickers."""

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            result = await expedition_scenario_service.get_status(session, vault_id)
            if result is None:
                typer.echo("No active exploration in this vault. Run 'uv run fo-cli expedition-scenario setup' first.")
                return
            for entry in result.explorations:
                typer.echo(f"Exploration {entry.exploration_id}: {entry.dweller_name} (level {entry.dweller_level})")
                typer.echo(f"  status: {entry.status}, time remaining: {entry.time_remaining_seconds}s")
                typer.echo(f"  open run site: {entry.open_run_site_id or 'none'}")
                typer.echo("  available sites:")
                for site in entry.available_sites:
                    typer.echo(f"    - {site.id} ({site.name})")

    try:
        asyncio.run(_run())
    except (ResourceNotFoundException, ValueError) as exc:
        detail = exc.detail if isinstance(exc, ResourceNotFoundException) else str(exc)
        typer.echo(f"Error: {detail}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        logger.exception("expedition-scenario status failed")
        typer.echo("Error: expedition-scenario status failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
