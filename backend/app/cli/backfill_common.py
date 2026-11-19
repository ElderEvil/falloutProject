"""Shared backfill CLI scaffolding: scope options, vault resolution, and an asyncio runner with uniform error handling."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

import typer
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.utils.exceptions import ResourceNotFoundException

VaultOption = Annotated[
    str | None,
    typer.Option(help="Vault UUID to limit scope; ignored when --all-active is set"),
]
AllActiveOption = Annotated[
    bool,
    typer.Option(help="Process all non-deleted vaults"),
]
MaxVaultsOption = Annotated[
    int | None,
    typer.Option(help="Maximum active vaults to process; omit for all"),
]


def validate_vault_uuid(value: str) -> None:
    try:
        UUID(value)
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid vault UUID: {value!r}") from exc


def require_vault_scope(vault: str | None, all_active: bool) -> None:
    if not vault and not all_active:
        raise ValueError("Either --vault or --all-active must be provided")


async def fetch_vault_id(session: AsyncSession, vault: str, *, not_found_message: str) -> UUID:
    try:
        vault_obj = await crud.vault.get(session, UUID(vault))
    except ResourceNotFoundException as exc:
        raise ValueError(not_found_message) from exc
    return vault_obj.id


async def resolve_vault_ids(
    session: AsyncSession,
    vault: str | None,
    all_active: bool,
    max_vaults: int | None = None,
) -> list[UUID]:
    if all_active:
        vault_ids = [vault_obj.id for vault_obj in await crud.vault.get_active_ordered(session)]
        return vault_ids if max_vaults is None else vault_ids[:max_vaults]
    if vault:
        return [await fetch_vault_id(session, vault, not_found_message=f"Vault {vault} not found or deleted")]
    raise ValueError("Pass --vault <UUID> or --all-active")


def run_backfill_command[T](
    run: Callable[[], Coroutine[Any, Any, T]],
    *,
    errors: tuple[type[Exception], ...] = (ValueError, typer.BadParameter),
) -> T:
    try:
        result = asyncio.run(run())
    except errors as exc:
        typer.echo(f"Backfill failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    return result


def echo_apply_status(apply: bool) -> None:
    typer.echo("Applied." if apply else "Dry run — pass --apply to persist.")
