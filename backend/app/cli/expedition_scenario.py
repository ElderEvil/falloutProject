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
    site_query = f"?siteId={result.discovered_site_id}" if result.discovered_site_id else ""
    typer.echo(
        f"Frontend: http://localhost:5173/vault/{result.vault.id}/exploration/{result.exploration.id}{site_query}"
    )
    if result.discovered_site_id:
        typer.echo(f"Site report: {result.discovered_site_id} (bell + toast; enter before arrival home)")
    _print_login(result.owner_email)


def _print_login(owner_email: str | None) -> None:
    if owner_email == settings.FIRST_SUPERUSER_EMAIL:
        typer.echo(f"Login: {owner_email} (superuser — use the FIRST_SUPERUSER_PASSWORD from your .env)")
    elif owner_email:
        typer.echo(f"Login: {owner_email}")


def _print_multi(result) -> None:
    typer.echo("Vault:")
    typer.echo(f"  id: {result.vault.id}")
    typer.echo(f"  number: {result.vault.number}")
    typer.echo(f"  created: {'yes (boosted)' if result.created_vault else 'no (existing)'}")
    for entry in result.entries:
        site = entry.available_sites[0] if entry.available_sites else None
        if entry.discovered_site_id:
            site = next(
                (candidate for candidate in entry.available_sites if candidate.id == entry.discovered_site_id),
                site,
            )
        typer.echo("Dweller:")
        gender = getattr(entry.dweller.gender, "value", entry.dweller.gender)
        typer.echo(f"  {entry.dweller.display_name} ({gender}, level {entry.dweller.level}, id {entry.dweller.id})")
        typer.echo(f"  exploration: {entry.exploration.id}")
        if site is not None:
            typer.echo(f"  site: {site.id} ({site.name})")
            if entry.discovered_site_id:
                typer.echo(f"  found: {entry.discovered_site_id} (bell + toast)")
            typer.echo(
                f"  Frontend: http://localhost:5173/vault/{result.vault.id}/exploration/"
                f"{entry.exploration.id}?siteId={site.id}"
            )
    _print_login(result.owner_email)


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
    duration_hours: Annotated[int, typer.Option("--duration-hours", help="Exploration duration in hours (1-24)")] = 1,
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
    discovered_site: Annotated[
        str | None,
        typer.Option("--discovered-site", help="Fast-forward to this site and notify the owner on the return leg"),
    ] = None,
    dweller_id: Annotated[
        UUID | None,
        typer.Option("--dweller-id", help="Use an existing dweller, preserving their level and SPECIAL"),
    ] = None,
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
                discovered_site_id=discovered_site,
                dweller_id=dweller_id,
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
def vault1(
    dwellers: Annotated[
        int | None,
        typer.Option(
            "--dwellers",
            min=1,
            max=12,
            help="How many named dwellers; default: one per selected site",
        ),
    ] = None,
    dweller_level: Annotated[int, typer.Option("--dweller-level", min=1, max=50)] = 5,
    duration_hours: Annotated[
        int,
        typer.Option("--duration-hours", min=1, max=24, help="Legacy journey length in hours"),
    ] = 24,
    outbound_hours: Annotated[
        int,
        typer.Option("--outbound-hours", min=1, max=12, help="Outbound window left after the site is reported"),
    ] = 8,
    special: Annotated[
        int | None,
        typer.Option("--special", min=1, max=10, help="Every SPECIAL stat; omit for varied profiles"),
    ] = None,
    sites: Annotated[
        str | None,
        typer.Option("--sites", help="Comma-separated site ids; defaults to every non-scenario site"),
    ] = None,
    vault_number: Annotated[int, typer.Option("--vault-number", min=1, max=999)] = 1,
    vault_id: Annotated[
        UUID | None,
        typer.Option("--vault-id", help="Target an existing vault (for example the active Vault 1)"),
    ] = None,
    user_email: Annotated[
        str | None,
        typer.Option("--user-email", help="Owner email (default: FIRST_SUPERUSER_EMAIL)"),
    ] = None,
    keep_existing: Annotated[
        bool,
        typer.Option("--keep-existing", help="Reuse Vault 1 instead of recreating it"),
    ] = False,
) -> None:
    """Create a fresh Vault 1 where every selected site is scouted and reported."""
    site_ids = [site.strip() for site in sites.split(",") if site.strip()] if sites else None

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            result = await expedition_scenario_service.setup_multi(
                session,
                vault_id=vault_id,
                vault_number=vault_number,
                user_email=user_email,
                dwellers=dwellers,
                dweller_level=dweller_level,
                duration_hours=duration_hours,
                special=special,
                site_ids=site_ids,
                recreate=not keep_existing,
                outbound_hours=outbound_hours,
            )
            _print_multi(result)

    try:
        asyncio.run(_run())
        typer.echo("✓ expedition-scenario vault1 complete.")
    except (ResourceNotFoundException, ValueError) as exc:
        detail = exc.detail if isinstance(exc, ResourceNotFoundException) else str(exc)
        typer.echo(f"Error: {detail}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        logger.exception("expedition-scenario vault1 failed")
        typer.echo("Error: expedition-scenario vault1 failed — see logs for details.", err=True)
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
