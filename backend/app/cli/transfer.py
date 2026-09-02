"""CLI for safely transferring dwellers between vaults."""

import asyncio
import logging
from typing import Annotated
from uuid import UUID

import typer

from app.db.session import async_session_maker
from app.services.transfer_service import transfer_service
from app.utils.exceptions import ResourceNotFoundException, ValidationException

app = typer.Typer(
    name="transfer",
    help="Safely move dwellers between vaults with relationship cleanup.",
    no_args_is_help=True,
)

logger = logging.getLogger(__name__)


@app.command("dweller")
def transfer_dweller(
    dweller_id: Annotated[UUID, typer.Argument(help="Dweller UUID to transfer")],
    to_vault: Annotated[UUID, typer.Option("--to", help="Destination vault UUID")],
) -> None:
    """Transfer a single dweller to another vault.

    Cleans up partner links and cross-vault relationships/pregnancies.
    The dweller is unassigned from its room and becomes idle in the new vault.
    """

    async def _run() -> None:
        async with async_session_maker() as session:
            try:
                dwellers = await transfer_service.transfer_dwellers(session, [dweller_id], to_vault)
                typer.echo(f"✓ Transferred {dwellers[0].first_name} {dwellers[0].last_name or ''} to {to_vault}")
            except (ValidationException, ResourceNotFoundException) as exc:
                typer.echo(f"Error: {exc.detail if hasattr(exc, 'detail') else exc}", err=True)
                raise typer.Exit(code=1) from None
            except ValueError as exc:
                typer.echo(f"Error: {exc}", err=True)
                raise typer.Exit(code=1) from None

    asyncio.run(_run())


@app.command("batch")
def transfer_batch(
    dweller_ids: Annotated[str, typer.Argument(help="Comma-separated dweller UUIDs")],
    to_vault: Annotated[UUID, typer.Option("--to", help="Destination vault UUID")],
) -> None:
    """Transfer multiple dwellers at once (keeps mutual relationships)."""
    try:
        ids = [UUID(x.strip()) for x in dweller_ids.split(",") if x.strip()]
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid UUID in list: {exc}") from exc

    if not ids:
        typer.echo("Error: no dweller IDs provided", err=True)
        raise typer.Exit(code=1)

    async def _run() -> None:
        async with async_session_maker() as session:
            try:
                dwellers = await transfer_service.transfer_dwellers(session, ids, to_vault)
                typer.echo(f"✓ Transferred {len(dwellers)} dwellers to {to_vault}")
                for d in dwellers:
                    typer.echo(f"  - {d.first_name} {d.last_name or ''} ({d.id})")
            except (ValidationException, ResourceNotFoundException) as exc:
                typer.echo(f"Error: {exc.detail if hasattr(exc, 'detail') else exc}", err=True)
                raise typer.Exit(code=1) from None

    asyncio.run(_run())


@app.command("cleanup")
def cleanup_vault(
    vault_id: Annotated[UUID, typer.Argument(help="Vault UUID to clean")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Confirm deletion")] = False,
) -> None:
    """Delete orphan cross-vault relationships for a vault (repair after manual edits)."""
    if not yes:
        typer.echo(
            "This will delete cross-vault relationships where dwellers belong to different vaults. Pass --yes to confirm."
        )
        raise typer.Exit(code=1)

    async def _run() -> None:
        async with async_session_maker() as session:
            count = await transfer_service.cleanup_cross_vault_relationships(session, vault_id)
            typer.echo(f"✓ Cleaned {count} cross-vault relationships for vault {vault_id}")

    asyncio.run(_run())
