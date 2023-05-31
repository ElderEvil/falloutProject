from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.api import deps
from app.api.deps import CurrentSuperuser
from app.db.session import get_async_session
from app.models.user import User
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultRead, VaultReadWithUser, VaultUpdate

router = APIRouter()


@router.post("/", response_model=Vault, status_code=201)
async def create_vault(
    vault_data: VaultCreate,
    db_session: AsyncSession = Depends(get_async_session),
    user: User = Depends(deps.get_current_active_user),
):
    return await crud.vault.create_with_user_id(db_session, vault_data, user.id)


@router.get("/", response_model=list[VaultReadWithUser])
async def read_vault_list(
    user: CurrentSuperuser,
    skip: int = 0,
    limit: int = 100,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.vault.get_multi(db_session, skip=skip, limit=limit)


@router.get("/my", response_model=list[VaultRead])
async def read_my_vaults(
    db_session: AsyncSession = Depends(get_async_session),
    user: User = Depends(deps.get_current_active_user),
):
    return await crud.vault.get_by_user_id(db_session, user_id=user.id)


@router.get("/{vault_id}", response_model=VaultReadWithUser)
async def read_vault(
    vault_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
    user: User = Depends(deps.get_current_active_superuser),
):
    return await crud.vault.get(db_session, vault_id)


@router.put("/{vault_id}", response_model=VaultReadWithUser)
async def update_vault(
    vault_id: UUID4,
    vault_data: VaultUpdate,
    db_session: AsyncSession = Depends(get_async_session),
    user: User = Depends(deps.get_current_active_user),
):
    vault = await crud.vault.get(db_session, vault_id)
    if vault.user_id != user.id or not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return await crud.vault.update(db_session, vault_id, vault_data)


@router.delete("/{vault_id}", status_code=204)
async def delete_vault(
    vault_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
    user: User = Depends(deps.get_current_active_user),
):
    vault = await crud.vault.get(db_session, vault_id)
    if vault.user_id != user.id or not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return await crud.vault.delete(db_session, vault_id)
