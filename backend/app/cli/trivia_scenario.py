"""CLI command group: trivia-scenario — one-command raider trivia demo.

Creates a vault with a Scout on an active legacy journey. Every level-eligible
expedition site is offered, so the same Scout can play the raider trivia and
every other site one by one. Profiles choose the Scout's power: demo (10/7),
balanced (5/4), or hard (3/3).
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
    help=(
        "Dev/QA: build a Vault 666 Scout who can play the raider trivia and every site one by one. "
        "Profiles: demo (10/7), balanced (5/4), hard (3/3)."
    ),
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)

PROFILES: dict[str, tuple[int, int]] = {
    "demo": (10, 7),
    "balanced": (5, 4),
    "hard": (3, 3),
}


def resolve_profile(profile: str, dweller_level: int | None, special: int | None) -> tuple[int, int]:
    key = profile.strip().lower()
    if key not in PROFILES:
        raise ValueError(f"Unknown profile {profile!r}; choose demo, balanced, or hard")
    base_level, base_special = PROFILES[key]
    return (
        dweller_level if dweller_level is not None else base_level,
        special if special is not None else base_special,
    )


def _print_setup(result, profile: str, special: int) -> None:
    exploration = result.exploration
    remaining_hours = exploration.time_remaining_seconds() / 3600
    typer.echo("Vault:")
    typer.echo(f"  id: {result.vault.id}")
    typer.echo(f"  number: {result.vault.number}")
    typer.echo(f"  created: {'yes (boosted)' if result.created_vault else 'no (existing)'}")
    typer.echo(f"Profile: {profile} (level {result.dweller.level}, SPECIAL {special})")
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
    profile: Annotated[
        str,
        typer.Option("--profile", help="demo (10/7), balanced (5/4), or hard (3/3)"),
    ] = "balanced",
    dweller_level: Annotated[int | None, typer.Option("--dweller-level", min=1, max=50)] = None,
    special: Annotated[int | None, typer.Option("--special", min=1, max=10, help="Every SPECIAL stat")] = None,
    duration_hours: Annotated[
        int,
        typer.Option("--duration-hours", min=1, max=24, help="Journey length in hours"),
    ] = 8,
) -> None:
    """Create a ready-to-play trivia scenario with every site available.

    Profiles: demo (level 10, SPECIAL 7), balanced (level 5, SPECIAL 4), hard
    (level 3, SPECIAL 3). Explicit --dweller-level/--special override the profile.
    """
    try:
        level, special_value = resolve_profile(profile, dweller_level, special)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
    profile_name = profile.strip().lower()

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            result = await expedition_scenario_service.setup(
                session,
                vault_id=vault_id,
                user_email=user_email,
                vault_number=None if vault_id is not None else vault_number,
                dweller_level=level,
                duration_hours=duration_hours,
                special=special_value,
                all_sites=True,
            )
            _print_setup(result, profile_name, special_value)

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
