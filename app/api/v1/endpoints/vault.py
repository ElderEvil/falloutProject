from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel import Session

from app import crud
from app.api import deps
from app.db.base import get_session
from app.models.user import User
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultRead, VaultUpdate

router = APIRouter()


@router.post("/", response_model=Vault, status_code=201)
def create_vault(
    vault_data: VaultCreate,
    db: Session = Depends(get_session),
    user: User = Depends(deps.get_current_active_user),
):
    vault_data.user_id = user.id
    return crud.vault.create(db, vault_data)


@router.get("/", response_model=list[VaultRead])
def read_vault_list(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_session),
    user: User = Depends(deps.get_current_active_superuser),
):
    return crud.vault.get_multi(db, skip=skip, limit=limit)


@router.get("/my", response_model=list[VaultRead])
def read_my_vaults(
    db: Session = Depends(get_session),
    user: User = Depends(deps.get_current_active_user),
):
    return crud.vault.get_by_user_id(db, user_id=user.id)


@router.get("/{vault_id}", response_model=VaultRead)
def read_vault(
    vault_id: UUID4,
    db: Session = Depends(get_session),
    user: User = Depends(deps.get_current_active_superuser),
):
    return crud.vault.get(db, vault_id)


@router.put("/{vault_id}", response_model=VaultRead)
def update_vault(
    vault_id: UUID4,
    vault_data: VaultUpdate,
    db: Session = Depends(get_session),
    user: User = Depends(deps.get_current_active_user),
):
    vault = crud.vault.get(db, vault_id)
    if vault.user_id != user.id or not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return crud.vault.update(db, vault_id, vault_data)


@router.delete("/{vault_id}", status_code=204)
def delete_vault(
    vault_id: UUID4,
    db: Session = Depends(get_session),
    user: User = Depends(deps.get_current_active_user),
):
    vault = crud.vault.get(db, vault_id)
    if vault.user_id != user.id or not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return crud.vault.delete(db, vault_id)
