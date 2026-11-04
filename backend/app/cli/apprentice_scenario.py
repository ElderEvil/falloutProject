"""CLI command group: apprentice-scenario — youth apprenticeship test setup."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import typer

from app.cli.scenario_common import run_scenario_command
from app.services.family.apprentice_scenario_service import apprentice_scenario_service

app = typer.Typer(
    name="apprentice-scenario",
    help="Dev/QA: create or inspect an idempotent youth apprenticeship scenario.",
    no_args_is_help=True,
)


def _print_status(*, prefix: str, result) -> None:
    apprentice = result.apprentice
    typer.echo(
        f"{prefix}: {apprentice.first_name} {apprentice.last_name or ''}".rstrip()
        + f" — {result.room.name} ({result.room.ability.value}), "
        + f"started {apprentice.apprentice_started_at.isoformat()}, "
        + ("ready for next tick" if result.ready else f"ready in {result.training_duration_seconds}s")
    )


@app.command()
def setup(
    vault_id: Annotated[UUID, typer.Option("--vault-id", help="Target vault UUID")],
    ready: Annotated[
        bool, typer.Option("--ready", help="Backdate the apprenticeship so its next tick can award a stat")
    ] = False,
) -> None:
    """Create one teen apprentice, or reuse the vault's existing active apprentice."""

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            result = await apprentice_scenario_service.setup(session, vault_id, ready=ready)
            _print_status(prefix="Created" if result.created else "Reused", result=result)

    run_scenario_command("apprentice-scenario setup", _run)


@app.command()
def status(
    vault_id: Annotated[UUID, typer.Option("--vault-id", help="Target vault UUID")],
) -> None:
    """Print the vault's current active youth apprenticeship, if present."""

    async def _run() -> None:
        from app.db.session import async_session_maker

        async with async_session_maker() as session:
            result = await apprentice_scenario_service.get_status(session, vault_id)
            if result is None:
                typer.echo("No active apprentice in this vault. Run 'uv run fo-cli apprentice-scenario setup' first.")
                return
            _print_status(prefix="Active apprentice", result=result)

    run_scenario_command("apprentice-scenario status", _run, success_message=False)


if __name__ == "__main__":
    app()
