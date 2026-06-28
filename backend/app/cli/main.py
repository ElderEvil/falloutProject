"""Unified CLI entry point for Fallout Shelter management commands.

Usage:
    uv run fo-cli --help
    uv run fo-cli createsuperuser
    uv run fo-cli migrations upgrade head
    uv run fo-cli startapp dweller
"""

import asyncio
import getpass
import logging
from typing import Annotated

import typer
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.cli.app.manage import startapp as _startapp
from app.cli.migrations.cli import migrations
from app.core.config import settings
from app.db.session import async_engine
from app.schemas.user import UserCreate

cli = typer.Typer(
    name="fo-cli",
    help="Fallout Shelter management CLI — user admin, migrations, scaffolding, and more.",
    no_args_is_help=True,
)

# Register sub-command groups
cli.add_typer(migrations, name="migrations", help="Alembic database migrations")

# Re-register startapp as a flat command
cli.command(name="startapp", help="Scaffold a new app module (model, schema, CRUD, API, service)")(_startapp)

logger = logging.getLogger(__name__)


def _make_async_session() -> sessionmaker:
    """Create a new async sessionmaker for CLI use."""
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@cli.command()
def createsuperuser(
    username: Annotated[str | None, typer.Option(prompt=True, help="Admin username")] = None,
    email: Annotated[str | None, typer.Option(prompt=True, help="Admin email address")] = None,
    password: Annotated[str | None, typer.Option(
        prompt=True,
        confirmation_prompt=True,
        hide_input=True,
        help="Admin password",
    )] = None,
    no_input: Annotated[bool, typer.Option(
        "--no-input",
        help="Skip prompts and use settings defaults (FIRST_SUPERUSER_*). Requires --username, --email, --password.",
    )] = False,
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
        # Fill in defaults from settings when user presses Enter at prompt
        if not username:
            username = settings.FIRST_SUPERUSER_USERNAME
            typer.echo(f"  Using default username: {username}")
        if not email:
            email = settings.FIRST_SUPERUSER_EMAIL
            typer.echo(f"  Using default email: {email}")

    async def _create() -> None:
        async_session = _make_async_session()
        async with async_session() as session:
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
        async_session = _make_async_session()
        async with async_session() as session:
            quest_count = await seed_quests_from_json(session)
            objective_count = await seed_objectives_from_json(session)
            typer.echo(f"  Quests seeded: {quest_count}")
            typer.echo(f"  Objectives seeded: {objective_count}")

    asyncio.run(_seed())
    typer.echo("✅ Seeding complete.")


if __name__ == "__main__":
    cli()
