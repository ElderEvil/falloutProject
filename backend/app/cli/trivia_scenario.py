"""CLI command group: trivia-scenario — one-command raider trivia demo.

Creates Vault 666 (or a chosen vault) with a strong Scout on an active legacy
journey. Every level-eligible expedition site is offered, so the same Scout can
play the raider trivia encounter and every other site one by one.
"""

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
    name="trivia-scenario",
    help="Dev/QA: build a Vault 666 Scout who can play the raider trivia and every site one by one.",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


def _print_setup(result) -> None:
    exploration = result.exploration
    remaining_hours = exploration.time_remaining_seconds() / 3600
    typer.echo("Vault:")
    typer.echo(f"  id: {result.vault.id}")
    typer.echo(f"  number: {result.vault.number}")
    typer.echo(f"  created: {'yes (boosted)' if result.created_vault else 'no (existing)'}")
    typer.echo("Dweller:")
    typer.echo(f"  {result.dweller.display_name} (level {result.dweller.level}, id {result.dweller.id})")
    typer.echo("Exploration:")
    typer.echo(f"  id: {exploration.id}")
    typer.echo(f"  status: {exploration.status.value}, remaining: {remaining_hours:.1f}h")
    typer.echo("Available sites (enter one by one):")
    for site in result.available_sites:
        typer.echo(f"  - {site.id} ({site.name}, min level {site.min_dweller_level})")
    typer.echo(
        f"Frontend: http://localhost:5173/vault/{result.vault.id}/exploration/{exploration.id}?siteId=raider_tollbooth"
    )
    if result.owner_email == settings.FIRST_SUPERUSER_EMAIL:
        typer.echo(f"Login: {result.owner_email} (superuser — use the FIRST_SUPERUSER_PASSWORD from your .env)")
    elif result.owner_email:
        typer.echo(f"Login: {result.owner_email}")


@app.command()
def setup(
    vault_id: Annotated[
        UUID | None,
        typer.Option("--vault-id", help="Reuse an existing vault instead of creating one"),
    ] = None,
    user_email: Annotated[
        str | None,
        typer.Option("--user-email", help="Owner email for a new vault (default: FIRST_SUPERUSER_EMAIL)"),
    ] = None,
    vault_number: Annotated[
        int,
        typer.Option("--vault-number", min=1, max=999, help="Number for a newly created vault"),
    ] = 666,
    dweller_level: Annotated[int, typer.Option("--dweller-level", min=1, max=50)] = 10,
    special: Annotated[int, typer.Option("--special", min=1, max=10, help="Every SPECIAL stat")] = 7,
    duration_hours: Annotated[
        int,
        typer.Option("--duration-hours", min=1, max=24, help="Journey length in hours"),
    ] = 8,
) -> None:
    """Create a ready-to-play trivia scenario with every site available."""

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            result = await expedition_scenario_service.setup(
                session,
                vault_id=vault_id,
                user_email=user_email,
                vault_number=None if vault_id is not None else vault_number,
                dweller_level=dweller_level,
                duration_hours=duration_hours,
                special=special,
                all_sites=True,
            )
            _print_setup(result)

    try:
        asyncio.run(_run())
        typer.echo("✓ trivia-scenario setup complete.")
    except (ResourceNotFoundException, ValueError) as exc:
        detail = exc.detail if isinstance(exc, ResourceNotFoundException) else str(exc)
        typer.echo(f"Error: {detail}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as exc:
        logger.exception("trivia-scenario setup failed")
        typer.echo("Error: trivia-scenario setup failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from exc
