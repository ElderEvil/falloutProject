"""Shared lock order for exploration and vault/site mutations."""

from typing import Literal, overload

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import exploration as crud_exploration
from app.crud import vault as crud_vault
from app.models.exploration import Exploration
from app.utils.exceptions import ResourceNotFoundException


@overload
async def lock_exploration_with_vault_claim(
    db_session: AsyncSession, exploration_id: UUID4, *, missing_ok: Literal[False] = False
) -> Exploration: ...


@overload
async def lock_exploration_with_vault_claim(
    db_session: AsyncSession, exploration_id: UUID4, *, missing_ok: Literal[True]
) -> Exploration | None: ...


async def lock_exploration_with_vault_claim(
    db_session: AsyncSession, exploration_id: UUID4, *, missing_ok: bool = False
) -> Exploration | None:
    """Claim the vault before locking its exploration; callers may then lock a run."""
    preview = await crud_exploration.get(db_session, exploration_id)
    if preview is None:
        if missing_ok:
            return None
        raise ResourceNotFoundException(Exploration, identifier=exploration_id)
    await crud_vault.get_for_update(db_session, preview.vault_id)
    exploration = await crud_exploration.get_for_update(db_session, exploration_id)
    if exploration is None and not missing_ok:
        raise ResourceNotFoundException(Exploration, identifier=exploration_id)
    return exploration
