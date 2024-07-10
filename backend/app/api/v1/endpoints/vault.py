from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser
from app.db.session import get_async_session
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultNumber, VaultReadWithNumbers, VaultReadWithUser, VaultUpdate

router = APIRouter()


@router.post("/", response_model=Vault, status_code=201)
async def create_vault(
    *,
    vault_data: VaultCreate,
    db_session: AsyncSession = Depends(get_async_session),
    user: CurrentActiveUser,
):
    return await crud.vault.create_with_user_id(db_session, vault_data, user.id)


@router.get("/", response_model=list[VaultReadWithUser])
async def read_vault_list(
    *,
    skip: int = 0,
    limit: int = 100,
    db_session: AsyncSession = Depends(get_async_session),
    _: CurrentSuperuser,
):
    return await crud.vault.get_multi(db_session, skip=skip, limit=limit)


@router.get("/my", response_model=list[VaultReadWithNumbers])
async def read_my_vaults(
    *,
    db_session: AsyncSession = Depends(get_async_session),
    user: CurrentActiveUser,
):
    return await crud.vault.get_vaults_with_room_and_dweller_count(db_session=db_session, user_id=user.id)


@router.get("/{vault_id}", response_model=VaultReadWithUser)
async def read_vault(
    *,
    vault_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
    _: CurrentSuperuser,
):
    return await crud.vault.get(db_session, vault_id)


@router.put("/{vault_id}", response_model=VaultReadWithUser)
async def update_vault(
    *,
    vault_id: UUID4,
    vault_data: VaultUpdate,
    db_session: AsyncSession = Depends(get_async_session),
    user: CurrentActiveUser,
):
    vault = await crud.vault.get(db_session, vault_id)
    if vault.user_id != user.id or not user.is_superuser:
        raise HTTPException(status_code=403, detail="User does not have permission to update the vault")
    return await crud.vault.update(db_session, vault_id, vault_data)


@router.delete("/{vault_id}", status_code=204)
async def delete_vault(
    *,
    vault_id: UUID4,
    db_session: AsyncSession = Depends(get_async_session),
    user: CurrentActiveUser,
):
    vault = await crud.vault.get(db_session, vault_id)
    if vault and (vault.user_id != user.id or not user.is_superuser):
        raise HTTPException(status_code=403, detail="User does not have permission to delete the vault")
    return await crud.vault.delete(db_session, vault_id)


@router.post("/initiate", response_model=Vault, status_code=201)
async def start_vault(
    *,
    vault_data: VaultNumber,
    db_session: AsyncSession = Depends(get_async_session),
    user: CurrentActiveUser,
):
    return await crud.vault.initiate(db_session=db_session, obj_in=vault_data, user_id=user.id)
