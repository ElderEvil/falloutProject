from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel import Session

from app import crud
from app.db.base import get_session
from app.models.vault import Vault
from app.schemas.vault import VaultCreate, VaultRead, VaultUpdate

router = APIRouter()


@router.post("/", response_model=Vault, status_code=201)
def create_vault(vault_data: VaultCreate, db: Session = Depends(get_session)):
    return crud.vault.create(db, vault_data)


@router.get("/", response_model=list[VaultRead])
def read_vault_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    return crud.vault.get_multi(db, skip=skip, limit=limit)


@router.get("/{vault_id}", response_model=VaultRead)
def read_vault(vault_id: UUID4, db: Session = Depends(get_session)):
    return crud.vault.get(db, vault_id)


@router.put("/{vault_id}", response_model=VaultRead)
def update_vault(vault_id: UUID4, vault_data: VaultUpdate, db: Session = Depends(get_session)):
    return crud.vault.update(db, vault_id, vault_data)


@router.delete("/{vault_id}", status_code=204)
def delete_vault(vault_id: UUID4, db: Session = Depends(get_session)):
    return crud.vault.delete(db, vault_id)
