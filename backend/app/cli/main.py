"""Unified CLI entry point for Fallout Shelter management commands.

Usage:
    uv run fo-cli --help
    uv run fo-cli createsuperuser
    uv run fo-cli seed
    uv run fo-cli seed-prompts
    uv run fo-cli version-prompt chat --template-file /path/to/chat-v2.txt
    uv run fo-cli merge-users --source <uuid|email|username> --target <uuid|email|username> [--apply]
    uv run fo-cli family-scenario --help
    uv run fo-cli apprentice-scenario --help
    uv run fo-cli expedition-scenario --help
    uv run fo-cli trivia-scenario --help
    uv run fo-cli backfill --help
    uv run fo-cli ops --help
    uv run fo-cli simulate-exploration --help
    uv run fo-cli wiki-images --help
    uv run fo-cli merge-users --source old@example.com --target new@example.com
    uv run fo-cli merge-users --source <uuid> --target <uuid> --apply --reason "duplicate account"
"""

import asyncio
import logging
from typing import Annotated

import typer
from redis.asyncio import Redis

from app import crud
from app.cli.apprentice_scenario import app as apprentice_scenario
from app.cli.backfills import app as backfills
from app.cli.debug import app as debug
from app.cli.dweller_bios import dweller_bios as _dweller_bios
from app.cli.expedition_scenario import app as expedition_scenario
from app.cli.family_scenario import app as family_scenario
from app.cli.jev_eval import app as jev_eval
from app.cli.map_scenario import app as map_scenario
from app.cli.ops import app as ops
from app.cli.pregen_dwellers import pregen_dwellers as _pregen_dwellers
from app.cli.seed_places import seed_places as _seed_places
from app.cli.simulate_exploration import simulate as simulate_exploration
from app.cli.simulate_happiness import simulate as simulate_happiness
from app.cli.simulate_incidents import simulate as simulate_incidents
from app.cli.simulate_resources import run as simulate_resources
from app.cli.transfer import app as transfer
from app.cli.trivia_scenario import app as trivia_scenario
from app.cli.wiki_images import app as wiki_images
from app.core.config import settings
from app.db.session import async_session_maker
from app.schemas.user import UserCreate
from app.services.account_merge_service import MergePreview, merge_users
from app.utils.exceptions import DomainError

cli = typer.Typer(
    name="fo-cli",
    help="Fallout Shelter management CLI — user admin, seeding, backfills, and ops.",
    no_args_is_help=True,
)

# Register sub-command groups
cli.add_typer(family_scenario, name="family-scenario", help="Dev/QA: build family/breeding test scenarios")
cli.add_typer(jev_eval, name="jev-eval", help="Dev/QA: measure Jev guardrail accuracy and calibrate thresholds")
cli.add_typer(apprentice_scenario, name="apprentice-scenario", help="Dev/QA: build youth apprenticeship test scenarios")
cli.add_typer(
    expedition_scenario,
    name="expedition-scenario",
    help="Dev/QA: build a playable interactive expedition-site scenario",
)
cli.add_typer(backfills, name="backfill", help="Retroactive backfill commands")
cli.add_typer(debug, name="debug", help="Dev/QA: emit game events, inspect objectives/evaluators, simulate builds")
cli.add_typer(map_scenario, name="map-scenario", help="Dev/QA: populate a vault's map with a place per site-type group")
cli.add_typer(ops, name="ops", help="One-off operations and infrastructure tasks")
cli.add_typer(transfer, name="transfer", help="Move dwellers between vaults safely")
cli.add_typer(
    trivia_scenario,
    name="trivia-scenario",
    help="Dev/QA: build a Vault 666 Scout who can play the raider trivia and every site one by one",
)
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

# Register seed-places as a flat command
cli.command(
    name="seed-places",
    help="Ensure canonical world-place registry rows from seed_places.json",
)(_seed_places)

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
    if no_input and (not username or not email or not password):
        typer.echo(
            "Error: --no-input requires --username, --email, and --password to be provided.",
            err=True,
        )
        raise typer.Exit(code=1)
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


@cli.command(name="seed-prompts")
def seed_prompts() -> None:
    """Seed the prompt registry with v1 agent instructions (skips existing names)."""
    from app.utils.seed_prompts import seed_prompts as seed_prompt_rows

    async def _seed() -> int:
        async with async_session_maker() as session:
            return await seed_prompt_rows(session)

    inserted = asyncio.run(_seed())
    typer.echo(f"  Prompts seeded: {inserted}")
    typer.echo("✅ Prompt seeding complete.")


@cli.command(name="version-prompt")
def version_prompt(
    prompt_name: Annotated[str, typer.Argument(help="Registered prompt name, e.g. chat")],
    template_file: Annotated[str, typer.Option(help="Path to the replacement instruction text")],
    description: Annotated[str | None, typer.Option(help="Optional replacement description")] = None,
) -> None:
    """Create and activate an immutable replacement prompt version."""
    from pathlib import Path

    from app.services.prompt_service import create_prompt_version

    template = Path(template_file).read_text()

    async def _version() -> int:
        async with async_session_maker() as session:
            prompt = await create_prompt_version(session, prompt_name, template, description=description)
            return prompt.version

    version = asyncio.run(_version())
    typer.echo(f"✅ Activated {prompt_name} v{version}.")


async def _close_merge_redis(redis_client: Redis | None) -> None:
    """Close the merge Redis client without masking an already-committed merge."""
    if redis_client is None:
        return
    try:
        await redis_client.aclose()
    except Exception:
        logger.warning("Failed to close the merge-users Redis client", exc_info=True)


def _print_merge_preview(preview: MergePreview) -> None:
    """Render a merge preview or the applied merge summary."""
    source_email = preview.source_email or "—"
    target_email = preview.target_email or "—"
    result_email = preview.result_email or "—"
    typer.echo(f"Source: {preview.source_username} <{source_email}> ({preview.source_id})")
    typer.echo(f"Target: {preview.target_username} <{target_email}> ({preview.target_id})")
    typer.echo("Moved counts:")
    for key in sorted(preview.moved_counts):
        typer.echo(f"  {key}: {preview.moved_counts[key]}")
    typer.echo(f"Vault numbers: {', '.join(map(str, preview.vault_numbers)) or 'none'}")
    typer.echo(f"Duplicate vault numbers: {', '.join(map(str, preview.duplicate_vault_numbers)) or 'none'}")
    typer.echo(f"OAuth conflicts: {', '.join(preview.oauth_conflicts) or 'none'}")
    tokens = preview.tokens_this_month
    typer.echo(f"Tokens this month: source={tokens.get('source', 0)} target={tokens.get('target', 0)}")
    typer.echo(f"Resulting email: {result_email}")
    typer.echo(f"Resulting username: {preview.result_username}")

    if preview.already_merged:
        typer.echo(f"Already merged (audit {preview.audit_id}).")
        return
    if preview.applied:
        typer.echo(f"Audit: {preview.audit_id}")
        typer.echo("Applied.")
    else:
        typer.echo("Dry run — pass --apply to persist.")
    if preview.token_invalidation_failed:
        typer.echo("Warning: the source refresh token could not be invalidated; check logs.", err=True)


@cli.command(name="merge-users")
def merge_users_command(
    source: Annotated[str, typer.Option(help="Source account: UUID, email, or username")],
    target: Annotated[str, typer.Option(help="Target account: UUID, email, or username")],
    actor: Annotated[
        str,
        typer.Option(help="Superuser performing the merge: UUID, email, or username"),
    ] = str(settings.FIRST_SUPERUSER_EMAIL),
    reason: Annotated[
        str | None,
        typer.Option(help="Merge reason (required with --apply)"),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option(help="Persist the merge; without it the command is a dry run"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Explicit dry-run mode (the default); cannot combine with --apply"),
    ] = False,
) -> None:
    """Preview or apply a one-way merge of a source account into a target account."""
    if apply and dry_run:
        typer.echo("Error: --apply and --dry-run cannot be used together.", err=True)
        raise typer.Exit(code=1)
    if apply and not (reason or "").strip():
        typer.echo("Error: --apply requires a non-empty --reason.", err=True)
        raise typer.Exit(code=1)

    effective_reason = (reason or "").strip() or "dry-run preview"

    async def _run() -> MergePreview:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True) if apply else None
        try:
            async with async_session_maker() as session:
                return await merge_users(
                    session,
                    source,
                    target,
                    actor=actor,
                    reason=effective_reason,
                    dry_run=not apply,
                    redis_client=redis_client,
                )
        finally:
            await _close_merge_redis(redis_client)

    try:
        preview = asyncio.run(_run())
    except DomainError as exc:
        typer.echo(f"Error: {exc.detail}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception:
        logger.exception("merge-users failed")
        typer.echo("Error: merge-users failed — see logs for details.", err=True)
        raise typer.Exit(code=1) from None

    _print_merge_preview(preview)


if __name__ == "__main__":
    cli()
