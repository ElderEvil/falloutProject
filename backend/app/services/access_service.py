"""Shared vault ownership policy for API dependencies and domain services."""

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models import Dweller, User, Vault
from app.schemas.dweller import DwellerReadFull
from app.utils.exceptions import AccessDeniedException


async def get_accessible_vault(vault_id: UUID4, user: User, db_session: AsyncSession) -> Vault:
    vault = await crud.vault.get(db_session, vault_id)
    if vault.user_id != user.id and not user.is_superuser:
        raise AccessDeniedException("The user doesn't have enough privileges")
    return vault


async def verify_dweller_access(dweller_id: UUID4, user: User, db_session: AsyncSession) -> Dweller:
    dweller = await crud.dweller.get(db_session, dweller_id)
    await get_accessible_vault(dweller.vault_id, user, db_session)
    return dweller


async def get_accessible_dweller(dweller_id: UUID4, user: User, db_session: AsyncSession) -> DwellerReadFull:
    dweller = await verify_dweller_access(dweller_id, user, db_session)
    return DwellerReadFull.model_validate(dweller)
