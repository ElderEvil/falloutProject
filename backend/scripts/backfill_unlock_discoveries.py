"""Retro-active discovery unlock backfill.

Links each DISCOVERY-type wasteland location to the dweller who found it
(exploration.dweller_id) with ``is_unlocked=True``. Discoveries created before
the discovery-unlock fix never created a dweller link, so they stayed locked on
the world map.

Usage:
    cd backend
    uv run python scripts/backfill_unlock_discoveries.py --vault <uuid>
    uv run python scripts/backfill_unlock_discoveries.py --all-active

Requires ASYNC_DATABASE_URI in backend/.env.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Annotated
from uuid import UUID

import typer
from sqlmodel import select

from app.crud.wasteland_location import wasteland_location as wl_crud
from app.db.session import async_session_maker
from app.models.wasteland_location import DwellerLocationRelationEnum, LocationTypeEnum, WastelandLocation

logger = logging.getLogger(__name__)


async def _unlock_discoveries_for_vault(session, vault_id: UUID) -> int:
    """Link every locked DISCOVERY location in a vault to its finding dweller."""
    from app.models.exploration import Exploration

    result = await session.execute(
        select(WastelandLocation).where(
            WastelandLocation.vault_id == vault_id,
            WastelandLocation.type == LocationTypeEnum.DISCOVERY,
            WastelandLocation.exploration_id.is_not(None),
        )
    )
    fixed = 0
    for location in result.scalars().all():
        exploration = await session.get(Exploration, location.exploration_id)
        if exploration is None:
            logger.warning("No exploration %s for location %s", location.exploration_id, location.name)
            continue
        await wl_crud.link_dweller(
            session,
            exploration.dweller_id,
            location.id,
            DwellerLocationRelationEnum.VISITED,
            is_unlocked=True,
        )
        fixed += 1
    return fixed


async def main(vault_uuid: str | None = None, all_active: bool = False) -> int | dict[UUID, int]:
    """Unlock discovery locations for one vault or all vaults."""
    from app.models.vault import Vault

    if not vault_uuid and not all_active:
        raise ValueError("Either --vault or --all-active must be provided")

    async with async_session_maker() as session:
        if all_active:
            vault_result = await session.execute(select(Vault.id).where(Vault.is_deleted.is_(False)))
            counts: dict[UUID, int] = {}
            for (vault_id,) in vault_result.all():
                counts[vault_id] = await _unlock_discoveries_for_vault(session, vault_id)
            return counts

        try:
            vault = await session.get(Vault, UUID(vault_uuid))
        except ValueError as exc:
            raise ValueError(f"Invalid vault UUID: {vault_uuid!r}") from exc
        if vault is None:
            raise ValueError(f"Vault {vault_uuid} not found")
        return await _unlock_discoveries_for_vault(session, vault.id)


app = typer.Typer(help="Unlock DISCOVERY locations by linking their finding dwellers.")


@app.command()
def backfill(
    vault: Annotated[
        str | None, typer.Option(help="Vault UUID to limit scope; ignored when --all-active is set")
    ] = None,
    all_active: Annotated[bool, typer.Option(help="Process all non-deleted vaults")] = False,
) -> None:
    """Link each DISCOVERY location to its finding dweller and mark it unlocked."""
    try:
        result = asyncio.run(main(vault_uuid=vault, all_active=all_active))
    except ValueError as exc:
        print(f"Backfill failed: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from exc

    if isinstance(result, dict):
        total = sum(result.values())
        print(f"Backfill complete: {total} discovery locations unlocked across {len(result)} vaults.")
        for vault_id, count in sorted(result.items()):
            print(f"  {vault_id}: {count}")
    else:
        print(f"Backfill complete: {result} discovery location(s) unlocked.")


def cli_entry() -> None:
    app()


if __name__ == "__main__":
    cli_entry()
