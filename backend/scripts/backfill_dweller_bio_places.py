"""Retro-active bio place backfill: extract origin/visited places from dweller bios
and register them on the world map via map_service.

Usage:
    cd backend
    uv run python scripts/backfill_dweller_bio_places.py
    uv run python scripts/backfill_dweller_bio_places.py --vault <uuid>
    uv run python scripts/backfill_dweller_bio_places.py --vault <uuid> --max-dwellers <n>
    uv run python scripts/backfill_dweller_bio_places.py --all-active --max-dwellers <n> --max-vaults <m>

Requires ASYNC_DATABASE_URI in backend/.env.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated
from uuid import UUID

import typer

from app import crud
from app.db.session import async_session_maker
from app.services.bio_place_backfill_service import bio_place_backfill_service

logger = logging.getLogger(__name__)

VAULT_ID = "f7a4d013-6252-4c19-b2ba-0bd499fe6133"
MAX_DWELLERS = 100  # safety limit per vault
MAX_VAULTS = 100  # safety limit for --all-active


# ---------------------------------------------------------------------------
# Main backfill logic
# ---------------------------------------------------------------------------


async def main(
    vault_uuid: str | None = None,
    max_dwellers: int = MAX_DWELLERS,
    all_active: bool = False,
    max_vaults: int = MAX_VAULTS,
) -> int | dict[UUID, int]:
    """Run the backfill for one vault or all active vaults.

    When *all_active* is True, every non-deleted vault is processed and a mapping
    of ``vault_id`` → processed dweller count is returned.

    When *all_active* is False, *vault_uuid* defaults to ``VAULT_ID`` and a
    single integer count is returned.
    """
    async with async_session_maker() as session:
        if all_active:
            return await bio_place_backfill_service.backfill_bio_places_for_active_vaults(
                session,
                max_dwellers_per_vault=max_dwellers,
                max_vaults=max_vaults,
            )

        effective_uuid = vault_uuid or VAULT_ID
        vault = await crud.vault.get(session, UUID(effective_uuid))
        if vault is None:
            logger.warning("Vault %s not found", effective_uuid)
            return 0

        return await bio_place_backfill_service.backfill_bio_places_for_vault(
            session,
            vault.id,
            max_dwellers=max_dwellers,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


app = typer.Typer(help="Backfill dweller bio places from bio text.")


@app.command()
def backfill(
    vault: Annotated[
        str | None,
        typer.Option(help="Vault UUID to limit scope; ignored when --all-active is set"),
    ] = None,
    max_dwellers: Annotated[int, typer.Option(help="Maximum dwellers to process per vault")] = MAX_DWELLERS,
    all_active: Annotated[bool, typer.Option(help="Process all active (non-deleted) vaults")] = False,
    max_vaults: Annotated[int, typer.Option(help="Maximum active vaults to process")] = MAX_VAULTS,
) -> None:
    """Extract origin/visited places from dweller bios and register them on the world map."""
    if vault and not all_active:
        try:
            UUID(vault)
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid vault UUID: {vault!r}") from exc

    result = asyncio.run(
        main(vault_uuid=vault, max_dwellers=max_dwellers, all_active=all_active, max_vaults=max_vaults)
    )

    if isinstance(result, dict):
        total = sum(result.values())
        print(f"Backfill complete: {total} dweller bio places registered across {len(result)} vaults.")
        for vault_id, count in sorted(result.items()):
            print(f"  {vault_id}: {count}")
    else:
        print(f"Backfill complete: {result} dweller bio places registered.")


def cli_entry() -> None:
    app()


if __name__ == "__main__":
    cli_entry()
