"""Shared lock order for exploration and vault/site mutations."""

from typing import Literal, overload
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import exploration as crud_exploration
from app.crud import vault as crud_vault
from app.models.exploration import Exploration
from app.utils.exceptions import ResourceNotFoundException


@overload
async def lock_exploration_with_vault_claim(
    db_session: AsyncSession,
    exploration_id: UUID,
    *,
    missing_ok: Literal[False] = False,
    vault_id: UUID | None = None,
) -> Exploration: ...


@overload
async def lock_exploration_with_vault_claim(
    db_session: AsyncSession,
    exploration_id: UUID,
    *,
    missing_ok: Literal[True],
    vault_id: UUID | None = None,
) -> Exploration | None: ...


async def lock_exploration_with_vault_claim(
    db_session: AsyncSession,
    exploration_id: UUID,
    *,
    missing_ok: bool = False,
    vault_id: UUID | None = None,
) -> Exploration | None:
    """Claim the vault before locking its exploration; callers may then lock a run.

    Pass ``vault_id`` when the caller already loaded the exploration for this
    vault: that skips the preview SELECT and goes straight to the locks.
    """
    if vault_id is None:
        preview = await crud_exploration.get(db_session, exploration_id)
        if preview is None:
            if missing_ok:
                return None
            raise ResourceNotFoundException(Exploration, identifier=exploration_id)
        vault_id = preview.vault_id
    await crud_vault.get_for_update(db_session, vault_id)
    exploration = await crud_exploration.get_for_update(db_session, exploration_id)
    if exploration is None and not missing_ok:
        raise ResourceNotFoundException(Exploration, identifier=exploration_id)
    return exploration
