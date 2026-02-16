from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403, verify_dweller_access
from app.api.game_data_deps import get_static_game_data
from app.crud.dweller import determine_status_for_room
from app.db.session import get_async_session
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerCreateWithoutVaultID,
    DwellerDeadRead,
    DwellerRead,
    DwellerReadFull,
    DwellerReadLess,
    DwellerReadWithRoomID,
    DwellerRename,
    DwellerReviveResponse,
    DwellerUpdate,
    DwellerVisualAttributesInput,
    RevivalCostResponse,
)
from app.services.death_service import death_service
from app.services.dweller_ai import dweller_ai
from app.services.happiness_service import happiness_service
from app.utils.exceptions import ContentNoChangeException

router = APIRouter()


@router.post("/", response_model=DwellerRead)
async def create_dweller(
    dweller_data: DwellerCreate,
    _: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.dweller.create(db_session, dweller_data)


@router.get("/", response_model=list[DwellerReadLess])
async def read_dweller_list(
    # vault_id: UUID4,
    _: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
):
    return await crud.dweller.get_multi(db_session=db_session, skip=skip, limit=limit)


@router.get("/{dweller_id}", response_model=DwellerReadFull)
async def read_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.get(db_session, dweller_id)


@router.put("/{dweller_id}", response_model=DwellerRead)
async def update_dweller(
    dweller_id: UUID4,
    dweller_data: DwellerUpdate,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await verify_dweller_access(dweller_id, user, db_session)
    # If room_id is being updated, automatically update status
    if dweller_data.room_id is not None or (
        hasattr(dweller_data, "model_fields_set") and "room_id" in dweller_data.model_fields_set
    ):
        if dweller_data.room_id is None:
            dweller_data.status = determine_status_for_room(None)
        else:
            room_obj = await crud.room.get(db_session, dweller_data.room_id)
            dweller_data.status = determine_status_for_room(room_obj.category)

    return await crud.dweller.update(db_session, dweller_id, dweller_data)


@router.patch("/{dweller_id}/rename", response_model=DwellerRead)
async def rename_dweller(
    dweller_id: UUID4,
    rename: DwellerRename,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Rename a dweller (first name only)."""

    await verify_dweller_access(dweller_id, user, db_session)
    dweller_data = DwellerUpdate(first_name=rename.first_name)
    return await crud.dweller.update(db_session, dweller_id, dweller_data)


@router.delete("/{dweller_id}", status_code=204)
async def delete_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    hard_delete: Annotated[bool, Query(description="If True, permanently delete. Otherwise soft delete.")] = False,
):
    """
    Delete a dweller. By default performs soft delete to preserve AI-generated content for recycling.
    Use hard_delete=True to permanently remove the dweller.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.delete(db_session, dweller_id, soft=not hard_delete)


@router.get("/vault/{vault_id}/", response_model=list[DwellerReadLess])
async def read_dwellers_by_vault(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
    status: DwellerStatusEnum | None = None,
    age_group: AgeGroupEnum | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
):
    """Get dwellers by vault with optional filtering by status, age group, search by name, and sorting."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.dweller.get_multi_by_vault(
        db_session=db_session,
        vault_id=vault_id,
        skip=skip,
        limit=limit,
        status=status,
        age_group=age_group,
        search=search,
        sort_by=sort_by,
        order=order,
    )


@router.post("/{dweller_id}/move_to/{room_id}", response_model=DwellerReadWithRoomID)
async def move_dweller_to_room(
    dweller_id: UUID4,
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.move_to_room(db_session, dweller_id, room_id)


@router.post("/create_random/", response_model=DwellerRead)
async def create_random_common_dweller(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    dweller_override: DwellerCreateCommonOverride | None = None,
):
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.dweller.create_random(db_session=db_session, obj_in=dweller_override, vault_id=vault_id)


@router.post("/{dweller_id}/generate_backstory/", response_model=DwellerReadFull)
async def generate_backstory(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await dweller_ai.generate_backstory(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/generate_visual_attributes/", response_model=DwellerReadFull)
async def generate_visual_attributes(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await dweller_ai.generate_visual_attributes(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/generate_photo/", response_model=DwellerReadFull)
async def generate_photo(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await dweller_ai.generate_photo(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/generate_audio/", response_model=DwellerReadFull)
async def generate_audio(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    text: str | None = None,
):
    return await dweller_ai.generate_audio(db_session=db_session, dweller_id=dweller_id, user=user, text=text)


@router.post("/{dweller_id}/generate_with_ai/", response_model=DwellerReadFull)
async def generate_data_with_ai(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    origin: str | None = None,
):
    return await dweller_ai.dweller_generate_pipeline(
        db_session=db_session, dweller_id=dweller_id, origin=origin, user=user
    )


@router.post("/{dweller_id}/generate_avatar", response_model=DwellerReadFull)
async def generate_dweller_avatar(
    dweller_id: UUID4,
    dweller_first_name: str,
    dweller_last_name: str,
    visual_attributes_input: DwellerVisualAttributesInput,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: CurrentActiveUser,
):
    return await dweller_ai.generate_dweller_avatar(
        db_session=db_session,
        dweller_id=dweller_id,
        dweller_first_name=dweller_first_name,
        dweller_last_name=dweller_last_name,
        visual_attributes_input=visual_attributes_input,
        user=current_user,
    )


@router.get("/read_data/", response_model=list[DwellerCreateWithoutVaultID])
async def read_dwellers_data(data_store=Depends(get_static_game_data)):
    return data_store.dwellers


@router.post("/{dweller_id}/use_stimpack", response_model=DwellerRead)
async def use_stimpack(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Use a stimpack to heal the dweller (restores 40% of max health)."""
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.use_stimpack(db_session, dweller_id)


@router.post("/{dweller_id}/use_radaway", response_model=DwellerRead)
async def use_radaway(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Use a radaway to remove radiation from the dweller (removes 50% of radiation)."""
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.use_radaway(db_session, dweller_id)


@router.get("/{dweller_id}/happiness_modifiers")
async def get_happiness_modifiers(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get detailed breakdown of happiness modifiers for a dweller."""
    await verify_dweller_access(dweller_id, user, db_session)
    return await happiness_service.get_happiness_modifiers(db_session, dweller_id)


@router.post("/{dweller_id}/auto_assign", response_model=DwellerReadWithRoomID)
async def auto_assign_to_room(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Auto-assign dweller to the best matching production room based on their highest SPECIAL stat."""
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.auto_assign_to_best_room(db_session, dweller_id)


# ============================================
# Death System Endpoints
# ============================================


@router.get("/vault/{vault_id}/dead", response_model=list[DwellerDeadRead])
async def get_dead_dwellers(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
):
    """Get all dead dwellers (revivable) for a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)
    dwellers = await crud.dweller.get_dead_dwellers(
        db_session, vault_id, include_permanent=False, skip=skip, limit=limit
    )

    # Enrich with days_until_permanent
    result = []
    for dweller in dwellers:
        dweller_data = DwellerDeadRead.model_validate(dweller)
        dweller_data.days_until_permanent = death_service.get_days_until_permanent(dweller)
        result.append(dweller_data)

    return result


@router.get("/vault/{vault_id}/graveyard", response_model=list[DwellerDeadRead])
async def get_graveyard(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
):
    """Get permanently dead dwellers (graveyard) for a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)
    dwellers = await crud.dweller.get_graveyard(db_session, vault_id, skip=skip, limit=limit)
    return [DwellerDeadRead.model_validate(dweller) for dweller in dwellers]


@router.get("/{dweller_id}/revival_cost", response_model=RevivalCostResponse)
async def get_revival_cost(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get the revival cost for a dead dweller."""
    await verify_dweller_access(dweller_id, user, db_session)
    dweller = await crud.dweller.get(db_session, dweller_id)

    if not dweller.is_dead:
        raise ContentNoChangeException(detail="Dweller is not dead")

    vault = await crud.vault.get(db_session, dweller.vault_id)
    revival_cost = death_service.get_revival_cost(dweller.level)

    return RevivalCostResponse(
        dweller_id=dweller.id,
        dweller_name=f"{dweller.first_name} {dweller.last_name or ''}".strip(),
        level=dweller.level,
        revival_cost=revival_cost,
        days_until_permanent=death_service.get_days_until_permanent(dweller),
        can_afford=vault.bottle_caps >= revival_cost,
        vault_caps=vault.bottle_caps,
    )


@router.post("/{dweller_id}/revive", response_model=DwellerReviveResponse)
async def revive_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Revive a dead dweller by paying the revival cost in caps."""
    await verify_dweller_access(dweller_id, user, db_session)

    # Get dweller to calculate cost before revival
    dweller = await crud.dweller.get(db_session, dweller_id)
    revival_cost = death_service.get_revival_cost(dweller.level)

    # Perform revival
    revived_dweller = await death_service.revive_dweller(db_session, dweller_id, user.id)

    # Get updated vault caps
    vault = await crud.vault.get(db_session, revived_dweller.vault_id)

    return DwellerReviveResponse(
        dweller=DwellerRead.model_validate(revived_dweller),
        caps_spent=revival_cost,
        remaining_caps=vault.bottle_caps,
    )


# ============================================================================
# Soft Delete Endpoints
# ============================================================================


@router.post("/{dweller_id}/soft-delete", response_model=DwellerRead)
async def soft_delete_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Soft delete a dweller, preserving their data for future use.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.soft_delete(db_session, dweller_id)


@router.post("/{dweller_id}/restore", response_model=DwellerRead)
async def restore_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Restore a soft-deleted dweller.
    """
    # Note: We need to verify access with include_deleted=True
    dweller = await crud.dweller.get(db_session, dweller_id, include_deleted=True)
    await get_user_vault_or_403(dweller.vault_id, user, db_session)
    return await crud.dweller.restore(db_session, dweller_id)


@router.get("/vault/{vault_id}/deleted", response_model=list[DwellerReadLess])
async def read_deleted_dwellers_by_vault(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
):
    """
    Get soft-deleted dwellers for a specific vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.dweller.get_deleted_by_vault(db_session=db_session, vault_id=vault_id, skip=skip, limit=limit)
