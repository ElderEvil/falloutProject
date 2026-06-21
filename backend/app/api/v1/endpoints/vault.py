from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.vault import Vault
from app.schemas.vault import (
    AutoAssignResponse,
    UnassignResponse,
    VaultCreate,
    VaultNumber,
    VaultReadWithNumbers,
    VaultReadWithUser,
    VaultUpdate,
)
from app.services.dweller_assignment_service import dweller_assignment_service
from app.services.vault_service import vault_service

router = APIRouter(prefix="/vaults", tags=["Vault"])


@router.post("/", response_model=Vault, status_code=201)
async def create_vault(
    *,
    vault_data: VaultCreate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    admin: CurrentSuperuser,
) -> Vault:
    return await crud.vault.create_with_user_id(db_session=db_session, obj_in=vault_data, user_id=admin.id)


@router.get("/", response_model=list[VaultReadWithUser])
async def read_vault_list(
    *,
    skip: int = 0,
    limit: int = 100,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> list[VaultReadWithUser]:
    return await crud.vault.get_multi(db_session, skip=skip, limit=limit)


@router.get("/my", response_model=list[VaultReadWithNumbers])
async def read_my_vaults(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> list[VaultReadWithNumbers]:
    return await crud.vault.get_vaults_with_room_and_dweller_count(db_session=db_session, user_id=user.id)


@router.get("/{vault_id}", response_model=VaultReadWithNumbers)
async def read_vault(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: Annotated[Vault, Depends(get_user_vault_or_403)],
) -> VaultReadWithNumbers:
    return await crud.vault.get_vault_with_room_and_dweller_count(db_session=db_session, vault_id=vault_id)


@router.put("/{vault_id}", response_model=VaultReadWithUser)
async def update_vault(
    *,
    vault_id: UUID4,
    vault_data: VaultUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: Annotated[Vault, Depends(get_user_vault_or_403)],
) -> VaultReadWithUser:
    return await crud.vault.update(db_session, vault_id, vault_data)


@router.delete("/{vault_id}", status_code=204)
async def delete_vault(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: Annotated[Vault, Depends(get_user_vault_or_403)],
    hard_delete: Annotated[bool, Query(description="If True, permanently delete. Otherwise soft delete.")] = False,
) -> None:
    """
    Delete a vault. By default performs soft delete to preserve data.
    Use hard_delete=True to permanently remove the vault.
    """
    return await crud.vault.delete(db_session, vault_id, soft=not hard_delete)


@router.post("/{vault_id}/toggle_game_state", response_model=Vault, status_code=200)
async def toggle_game_state(
    *,
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Vault:
    return await crud.vault.toggle_game_state(db_session=db_session, vault_id=vault.id)


@router.post("/initiate", response_model=Vault, status_code=201)
async def start_vault(
    *,
    vault_data: VaultNumber,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> Vault:
    is_boosted = vault_data.boosted or user.is_superuser
    return await vault_service.initiate_vault(
        db_session=db_session, obj_in=vault_data, user_id=user.id, is_boosted=is_boosted
    )


@router.post("/update_resources", status_code=200)
async def update_vault_resources(
    *,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
):
    return await vault_service.update_vault_resources(db_session=db_session, vault_id=vault_id)


@router.post("/{vault_id}/dwellers/unassign-all", response_model=UnassignResponse)
async def unassign_all_dwellers(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> UnassignResponse:
    """Unassign all dwellers from their rooms in the specified vault."""
    result = await dweller_assignment_service.unassign_all_dwellers(db_session, vault.id)
    return UnassignResponse(**result)


@router.post("/{vault_id}/dwellers/auto-assign-production", response_model=AutoAssignResponse)
async def auto_assign_production_rooms(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AutoAssignResponse:
    """
    Intelligently assign unassigned dwellers to production rooms based on SPECIAL stats.

    Priority order: Power Plant (Strength) → Diner (Agility) → Water Treatment (Perception)
    Dwellers are matched to rooms based on their relevant SPECIAL stat (highest stat dwellers assigned first).
    """
    result = await dweller_assignment_service.auto_assign_production_rooms(db_session, vault.id)
    return AutoAssignResponse(**result)


@router.post("/{vault_id}/dwellers/auto-assign-all", response_model=AutoAssignResponse)
async def auto_assign_all_rooms(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AutoAssignResponse:
    """
    Intelligently assign unassigned dwellers to ALL room types based on SPECIAL stats.

    Priority order:
    1. Production rooms (Strength: Power, Perception: Water, Agility: Food) - most critical
    2. Med/Science rooms (Intelligence) - medical and research services
    3. Radio rooms (Charisma) - recruitment and happiness
    4. Training rooms (all 7 SPECIAL stats) - for development

    Within each tier, dwellers are distributed proportionally to room capacities.
    Dwellers are matched to rooms based on their relevant SPECIAL stat (highest stat dwellers assigned first).
    """
    result = await dweller_assignment_service.auto_assign_all_rooms(db_session, vault.id)
    return AutoAssignResponse(**result)
