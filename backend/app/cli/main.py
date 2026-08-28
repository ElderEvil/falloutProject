"""Unified CLI entry point for Fallout Shelter management commands.

Usage:
    uv run fo-cli --help
    uv run fo-cli createsuperuser
    uv run fo-cli seed
    uv run fo-cli family-scenario --help
    uv run fo-cli backfill --help
    uv run fo-cli ops --help
    uv run fo-cli simulate-exploration --help
    uv run fo-cli wiki-images --help
"""

import asyncio
import logging
from typing import Annotated

import typer

from app import crud
from app.cli.app.backfills import app as backfills
from app.cli.app.dweller_bios import dweller_bios as _dweller_bios
from app.cli.app.family_scenario import app as family_scenario
from app.cli.app.ops import app as ops
from app.cli.app.pregen_dwellers import pregen_dwellers as _pregen_dwellers
from app.cli.app.simulate_exploration import simulate as simulate_exploration
from app.cli.app.simulate_happiness import simulate as simulate_happiness
from app.cli.app.simulate_incidents import simulate as simulate_incidents
from app.cli.app.simulate_resources import run as simulate_resources
from app.cli.app.wiki_images import app as wiki_images
from app.core.config import settings
from app.db.session import async_session_maker
from app.schemas.user import UserCreate

cli = typer.Typer(
    name="fo-cli",
    help="Fallout Shelter management CLI — user admin, seeding, backfills, and ops.",
    no_args_is_help=True,
)

# Register sub-command groups
cli.add_typer(family_scenario, name="family-scenario", help="Dev/QA: build family/breeding test scenarios")
cli.add_typer(backfills, name="backfill", help="Retroactive backfill commands")
cli.add_typer(ops, name="ops", help="One-off operations and infrastructure tasks")
cli.add_typer(wiki_images, name="wiki-images", help="Download Fallout Shelter wiki image assets")
cli.command(name="simulate-exploration", help="Run the multi-system balance simulator")(simulate_exploration)
cli.command(name="simulate-happiness", help="Run the happiness balance simulator")(simulate_happiness)
cli.command(name="simulate-incidents", help="Run the incident balance simulator")(simulate_incidents)
cli.command(name="simulate-resources", help="Run the resource economy simulator")(simulate_resources)

# Re-register pregen-dwellers as a flat command
cli.command(name="pregen-dwellers", help="Dev/QA: seed dwellers with deterministic bios + world-map place markers")(
    _pregen_dwellers
)

# Re-register dweller-bios as a flat command
cli.command(
    name="dweller-bios",
    help="Dev/QA: fill missing bios for existing dwellers + world-map place markers",
)(_dweller_bios)

logger = logging.getLogger(__name__)


@cli.command()
def createsuperuser(
    username: Annotated[str | None, typer.Option(help="Admin username")] = None,
    email: Annotated[str | None, typer.Option(help="Admin email address")] = None,
    password: Annotated[
        str | None,
        typer.Option(
            confirmation_prompt=True,
            hide_input=True,
            help="Admin password",
        ),
    ] = None,
    no_input: Annotated[
        bool,
        typer.Option(
            "--no-input",
            help="Skip prompts and use settings defaults (FIRST_SUPERUSER_*). Requires --username, --email, --password.",
        ),
    ] = False,
) -> None:
    """Create an admin superuser interactively or via flags.

    Prompts for username, email, and password interactively, or pass
    --no-input with --username/--email/--password to run non-interactively.
    Falls back to settings.FIRST_SUPERUSER_* values when not provided.
    """
    if no_input:
        if not all([username, email, password]):
            typer.echo(
                "Error: --no-input requires --username, --email, and --password to be provided.",
                err=True,
            )
            raise typer.Exit(code=1)
    else:
        # Prompt interactively
        if not username:
            username = typer.prompt("Admin username", default=settings.FIRST_SUPERUSER_USERNAME)
        if not email:
            email = typer.prompt("Admin email address", default=settings.FIRST_SUPERUSER_EMAIL)
        if not password:
            password = typer.prompt(
                "Admin password", confirmation_prompt=True, hide_input=True, default=settings.FIRST_SUPERUSER_PASSWORD
            )

    async def _create() -> None:
        async with async_session_maker() as session:
            # Check if user already exists
            existing = await crud.user.get_by_email(db_session=session, email=email)
            if existing:
                typer.echo(f"Error: User with email '{email}' already exists (id={existing.id}).", err=True)
                raise typer.Exit(code=1)

            existing_username = await crud.user.get_by_username(db_session=session, username=username)
            if existing_username:
                typer.echo(f"Error: Username '{username}' is already taken.", err=True)
                raise typer.Exit(code=1)

            user_in = UserCreate(
                username=username,
                email=email,
                password=password,
                is_superuser=True,
            )
            user = await crud.user.create(db_session=session, obj_in=user_in)
            typer.echo(f"✅ Superuser '{user.username}' created (id={user.id}).")

    asyncio.run(_create())


@cli.command()
def seed() -> None:
    """Re-seed quests and objectives from JSON files into the database."""
    from app.utils.seed_objectives import seed_objectives_from_json
    from app.utils.seed_quests import seed_quests_from_json

    async def _seed() -> None:
        async with async_session_maker() as session:
            quest_count = await seed_quests_from_json(session)
            objective_count = await seed_objectives_from_json(session)
            typer.echo(f"  Quests seeded: {quest_count}")
            typer.echo(f"  Objectives seeded: {objective_count}")

    asyncio.run(_seed())
    typer.echo("✅ Seeding complete.")


if __name__ == "__main__":
    cli()
