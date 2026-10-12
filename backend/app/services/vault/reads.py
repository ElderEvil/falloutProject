"""Vault reads: vault-with-counts assembly for the vault list and detail contracts."""

from itertools import starmap

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.vault import vault as vault_crud
from app.models.vault import Vault
from app.schemas.vault import VaultReadWithNumbers
from app.utils.resource_warnings import get_resource_warnings


def vault_with_numbers(
    vault_obj: Vault, room_count: int, dweller_count: int, stimpack: int, radaway: int
) -> VaultReadWithNumbers:
    return VaultReadWithNumbers(
        **vault_obj.model_dump(),
        room_count=room_count,
        dweller_count=dweller_count,
        stimpack=stimpack,
        radaway=radaway,
        resource_warnings=get_resource_warnings(
            vault_obj,
            {
                "power": float(vault_obj.power),
                "food": float(vault_obj.food),
                "water": float(vault_obj.water),
            },
        ),
    )


async def get_vaults_with_room_and_dweller_count(
    *, db_session: AsyncSession, user_id: UUID4
) -> list[VaultReadWithNumbers]:
    """List the user's non-deleted vaults with room/dweller counts and resource warnings."""
    return list(
        starmap(vault_with_numbers, await vault_crud.get_vault_count_rows(db_session=db_session, user_id=user_id))
    )


async def get_vault_with_room_and_dweller_count(*, db_session: AsyncSession, vault_id: UUID4) -> VaultReadWithNumbers:
    """Fetch a single vault with room/dweller counts and resource warnings."""
    vault_obj, room_count, dweller_count, stimpack, radaway = await vault_crud.get_vault_count_row(
        db_session=db_session, vault_id=vault_id
    )
    return vault_with_numbers(vault_obj, room_count, dweller_count, stimpack, radaway)
