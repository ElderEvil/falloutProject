"""Dweller endpoints."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403, verify_dweller_access
from app.core.enums import AgeGroupEnum, DwellerStatusEnum, FactionEnum, RaceEnum
from app.core.game_data import get_static_game_data
from app.db.session import get_async_session
from app.models.dweller import Dweller
from app.schemas.dweller import (
    BioAddendumRequest,
    DwellerAppearanceOptions,
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerCreateWithoutVaultID,
    DwellerDeadRead,
    DwellerIdentityOptions,
    DwellerRead,
    DwellerReadFull,
    DwellerReadLess,
    DwellerReadWithRoomID,
    DwellerRename,
    DwellerReviveResponse,
    DwellerUpdate,
    DwellerUpdateRequest,
    DwellerVisualAttributes,
    LineageResponse,
    RevivalCostResponse,
)
from app.schemas.exit_request import ExitDecisionResponse, ExitRequestRead
from app.schemas.happiness import HappinessModifiersResponse
from app.services import jev_service, medical_service
from app.services.bio_service import bio_service
from app.services.content_moderation_service import moderate_player_text
from app.services.dweller_ai import dweller_ai
from app.services.dweller_service import dweller_service
from app.services.exit_request_service import exit_request_service
from app.services.family.death_service import death_service
from app.services.family.lineage_service import lineage_service
from app.services.happiness_service import happiness_service
from app.utils.exceptions import ResourceNotFoundException
from app.utils.static_data import StaticGameData

router = APIRouter(prefix="/dwellers", tags=["Dweller"])


@router.post("/", response_model=DwellerRead)
async def create_dweller(
    dweller_data: DwellerCreate,
    _: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Dweller:
    """Create a new dweller.

    Returns:
        DwellerRead: The created dweller.
    """
    return await dweller_service.create_dweller(db_session, dweller_data)


@router.get("/", response_model=list[DwellerReadLess])
async def read_dweller_list(
    # vault_id: UUID4,
    _: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
) -> Sequence[Dweller]:
    """Retrieve a paginated list of dwellers.

    Returns:
        list[DwellerReadLess]: List of dwellers.
    """
    return await crud.dweller.get_multi(db_session=db_session, skip=skip, limit=limit)


@router.get("/identity-options", response_model=DwellerIdentityOptions)
async def read_identity_options(_: CurrentActiveUser) -> DwellerIdentityOptions:
    """Return the valid race, faction and state-of-being identity combinations."""
    return dweller_service.get_identity_options()


@router.get("/appearance-options", response_model=DwellerAppearanceOptions)
async def read_appearance_options(_: CurrentActiveUser) -> DwellerAppearanceOptions:
    """Return the canonical appearance choices for the appearance editor."""
    return dweller_service.get_appearance_options()


@router.get("/{dweller_id}", response_model=DwellerReadFull)
async def read_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Dweller:
    """Get full details for a specific dweller.

    Returns:
        DwellerReadFull: Full dweller details.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.get(db_session, dweller_id)


@router.get("/{dweller_id}/lineage", response_model=LineageResponse)
async def get_dweller_lineage(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> LineageResponse:
    """Get the computed family lineage for a dweller.

    Returns:
        LineageResponse: Parents, children, siblings, partners and generation.

    Raises:
        HTTPException: 404 if dweller not found.
        HTTPException: 403 if user doesn't have access.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    try:
        return await lineage_service.get_lineage(db_session, dweller_id)
    except ResourceNotFoundException:
        raise HTTPException(status_code=404, detail="Dweller not found") from None


@router.put("/{dweller_id}", response_model=DwellerRead)
async def update_dweller(
    dweller_id: UUID4,
    dweller_data: DwellerUpdateRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Dweller:
    """Update a dweller's player-editable fields.

    Game state (health, radiation, level, experience, supplies, status, death) is
    not accepted here — see `DwellerUpdateRequest`. Room assignment only happens
    via the dedicated move endpoints (`POST /dwellers/{id}/move_to/{room_id}`,
    auto_assign); this endpoint only accepts `room_id: null` to unassign.

    Returns:
        DwellerRead: The updated dweller.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await dweller_service.update_dweller(db_session=db_session, dweller_id=dweller_id, dweller_data=dweller_data)


@router.patch("/{dweller_id}/rename", response_model=DwellerRead)
async def rename_dweller(
    dweller_id: UUID4,
    rename: DwellerRename,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Dweller:
    """Rename a dweller (first name only).

    Returns:
        DwellerRead: The renamed dweller.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    if jev_service.is_configured():
        await moderate_player_text(rename.first_name, field="name")
    dweller_data = DwellerUpdate(first_name=rename.first_name)
    return await crud.dweller.update(db_session, dweller_id, dweller_data)


@router.delete("/{dweller_id}", status_code=204)
async def delete_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    hard_delete: Annotated[bool, Query(description="If True, permanently delete. Otherwise soft delete.")] = False,
) -> None:
    """Delete a dweller.

    By default performs soft delete to preserve AI-generated content for recycling.
    Use hard_delete=True to permanently remove the dweller.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    await crud.dweller.delete(db_session, dweller_id, soft=not hard_delete)


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
    race: RaceEnum | None = None,
    faction: FactionEnum | None = None,
    sort_by: str = "created_at",
    order: str = "desc",
) -> Sequence[Dweller]:
    """Get dwellers by vault with optional filtering and sorting.

    Returns:
        list[DwellerReadLess]: Filtered list of dwellers.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await dweller_service.list_vault_dwellers(
        db_session=db_session,
        vault_id=vault_id,
        skip=skip,
        limit=limit,
        status=status,
        age_group=age_group,
        search=search,
        race=race,
        faction=faction,
        sort_by=sort_by,
        order=order,
    )


@router.post("/{dweller_id}/move_to/{room_id}", response_model=DwellerReadWithRoomID)
async def move_dweller_to_room(
    dweller_id: UUID4,
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerReadWithRoomID:
    """Move a dweller to a specific room.

    Returns:
        DwellerReadWithRoomID: The dweller with updated room assignment.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    moved = await dweller_service.move_to_room(db_session, dweller_id, room_id)
    if moved is None:
        raise ResourceNotFoundException(Dweller, identifier=dweller_id)
    return moved


@router.post("/create_random/", response_model=DwellerRead)
async def create_random_common_dweller(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    dweller_override: DwellerCreateCommonOverride | None = None,
) -> Dweller:
    """Create a random common dweller for a vault.

    Returns:
        DwellerRead: The newly created random dweller.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await dweller_service.create_random_dweller(db_session, vault_id, dweller_override)


@router.post("/{dweller_id}/generate_backstory/", response_model=DwellerReadFull)
async def generate_backstory(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerReadFull:
    """Generate a backstory for a dweller using AI.

    Returns:
        DwellerReadFull: The dweller with generated backstory.
    """
    return await dweller_ai.generate_backstory(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/extend_bio/", response_model=DwellerReadFull)
async def extend_bio(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerReadFull:
    """Append new AI-generated detail to a dweller's existing biography."""
    return await dweller_ai.extend_bio(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/bio/addendum/", response_model=DwellerReadFull)
async def add_bio_addendum(
    dweller_id: UUID4,
    request: BioAddendumRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerReadFull:
    """Record a player-confirmed conversation detail into the dweller's biography."""
    await verify_dweller_access(dweller_id, user, db_session)
    if jev_service.is_configured():
        await moderate_player_text(request.text, field="bio text")
    await bio_service.append_entry(db_session, dweller_id, "dialogue", request.text, ref={"source": "chat"})
    return await crud.dweller.get_full_info(db_session, dweller_id)


@router.post("/{dweller_id}/generate_visual_attributes/", response_model=DwellerReadFull)
async def generate_visual_attributes(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerReadFull:
    """Generate visual attributes for a dweller using AI.

    Returns:
        DwellerReadFull: The dweller with generated visual attributes.
    """
    return await dweller_ai.generate_visual_attributes(db_session=db_session, dweller_id=dweller_id, user=user)


@router.post("/{dweller_id}/generate_photo/", response_model=DwellerReadFull)
async def generate_photo(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    force: Annotated[bool, Query(description="Regenerate even if a photo already exists")] = False,
) -> DwellerReadFull:
    """Generate a photo for a dweller using AI.

    Returns:
        DwellerReadFull: The dweller with generated photo.
    """
    return await dweller_ai.generate_photo(db_session=db_session, dweller_id=dweller_id, user=user, force=force)


@router.post("/{dweller_id}/generate_audio/", response_model=DwellerReadFull)
async def generate_audio(
    dweller_id: UUID4,
    text: str,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerReadFull:
    """Generate audio for a dweller using AI.

    Returns:
        DwellerReadFull: The dweller with generated audio.
    """
    return await dweller_ai.generate_audio(db_session=db_session, dweller_id=dweller_id, user=user, text=text)


@router.post("/{dweller_id}/generate_with_ai/", response_model=DwellerReadFull)
async def generate_data_with_ai(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    origin: str | None = None,
) -> DwellerReadFull:
    """Run the full AI generation pipeline for a dweller.

    Returns:
        DwellerReadFull: The dweller with all AI-generated data.
    """
    return await dweller_ai.dweller_generate_pipeline(
        db_session=db_session, dweller_id=dweller_id, origin=origin, user=user
    )


@router.post("/{dweller_id}/generate_avatar", response_model=DwellerReadFull)
async def generate_dweller_avatar(
    dweller_id: UUID4,
    dweller_first_name: str,
    dweller_last_name: str,
    visual_attributes_input: DwellerVisualAttributes,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    current_user: CurrentActiveUser,
) -> DwellerReadFull:
    """Generate an avatar for a dweller using AI.

    Returns:
        DwellerReadFull: The dweller with generated avatar.
    """
    return await dweller_ai.generate_dweller_avatar(
        db_session=db_session,
        dweller_id=dweller_id,
        dweller_first_name=dweller_first_name,
        dweller_last_name=dweller_last_name,
        visual_attributes_input=visual_attributes_input,
        user=current_user,
    )


@router.get("/read_data/", response_model=list[DwellerCreateWithoutVaultID])
async def read_dwellers_data(
    data_store: Annotated[StaticGameData, Depends(get_static_game_data)],
    _: CurrentActiveUser,
) -> Sequence[DwellerCreateWithoutVaultID]:
    """Get static dweller creation data.

    Returns:
        list[DwellerCreateWithoutVaultID]: List of dweller templates.
    """
    return data_store.dwellers


@router.post("/{dweller_id}/use_stimpack", response_model=DwellerRead)
async def use_stimpack(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Dweller:
    """Use one of the dweller's stimpacks to heal them.

    Returns:
        DwellerRead: The healed dweller.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await medical_service.use_stimpack(db_session, dweller_id)


@router.post("/{dweller_id}/use_radaway", response_model=DwellerRead)
async def use_radaway(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Dweller:
    """Use one of the dweller's RadAways to reduce their radiation.

    Returns:
        DwellerRead: The dweller with reduced radiation.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await medical_service.use_radaway(db_session, dweller_id)


@router.get("/{dweller_id}/happiness_modifiers", response_model=HappinessModifiersResponse)
async def get_happiness_modifiers(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> HappinessModifiersResponse:
    """Get detailed breakdown of happiness modifiers for a dweller.

    Returns:
        HappinessModifiersResponse: Happiness modifier breakdown.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    data = await happiness_service.get_happiness_modifiers(db_session, dweller_id)
    return HappinessModifiersResponse(**data)


@router.post("/{dweller_id}/auto_assign", response_model=DwellerReadWithRoomID)
async def auto_assign_to_room(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerReadWithRoomID:
    """Auto-assign dweller to the best matching production room based on their highest SPECIAL stat.

    Returns:
        DwellerReadWithRoomID: The dweller with assigned room.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    assigned = await dweller_service.auto_assign_to_best_room(db_session, dweller_id)
    if assigned is None:
        raise ResourceNotFoundException(Dweller, identifier=dweller_id)
    return assigned


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
) -> list[DwellerDeadRead]:
    """Get all dead dwellers (revivable) for a vault.

    Returns:
        list[DwellerDeadRead]: List of revivable dead dwellers with days until permanent death.
    """
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
) -> list[DwellerDeadRead]:
    """Get permanently dead dwellers (graveyard) for a vault.

    Returns:
        list[DwellerDeadRead]: List of permanently dead dwellers.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    dwellers = await crud.dweller.get_graveyard(db_session, vault_id, skip=skip, limit=limit)
    return [DwellerDeadRead.model_validate(dweller) for dweller in dwellers]


@router.get("/{dweller_id}/revival_cost", response_model=RevivalCostResponse)
async def get_revival_cost(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> RevivalCostResponse:
    """Get the revival cost for a dead dweller.

    Returns:
        RevivalCostResponse: Revival cost details and affordability.

    Raises:
        ContentNoChangeException: If the dweller is not dead.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await death_service.build_revival_quote(db_session, dweller_id, user)


@router.post("/{dweller_id}/revive", response_model=DwellerReviveResponse)
async def revive_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DwellerReviveResponse:
    """Revive a dead dweller by paying the revival cost in caps.

    Returns:
        DwellerReviveResponse: Revived dweller, caps spent, and remaining caps.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await death_service.revive_dweller(db_session, dweller_id, user)


# ============================================================================
# Soft Delete Endpoints
# ============================================================================


@router.post("/{dweller_id}/soft-delete", response_model=DwellerRead)
async def soft_delete_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Dweller:
    """Soft delete a dweller, preserving their data for future use.

    Returns:
        DwellerRead: The soft-deleted dweller.
    """
    await verify_dweller_access(dweller_id, user, db_session)
    return await crud.dweller.soft_delete(db_session, dweller_id)


@router.post("/{dweller_id}/restore", response_model=DwellerRead)
async def restore_dweller(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Dweller:
    """Restore a soft-deleted dweller.

    Returns:
        DwellerRead: The restored dweller.
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
) -> Sequence[Dweller]:
    """Get soft-deleted dwellers for a specific vault.

    Returns:
        list[DwellerReadLess]: List of soft-deleted dwellers.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.dweller.get_deleted_by_vault(db_session=db_session, vault_id=vault_id, skip=skip, limit=limit)


# ============================================================================
# Exit Requests — dwellers who ask to leave the vault. Granting is one-way.
# ============================================================================


def _to_exit_request_read(dweller: Dweller) -> ExitRequestRead:
    return ExitRequestRead(
        dweller_id=dweller.id,
        dweller_name=dweller.display_name,
        thumbnail_url=dweller.thumbnail_url,
        level=dweller.level,
        happiness=dweller.happiness,
        requested_at=dweller.exit_requested_at,
    )


@router.get("/vault/{vault_id}/exit-requests", response_model=list[ExitRequestRead])
async def list_exit_requests(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[ExitRequestRead]:
    """List dwellers waiting on an answer to their request to leave.

    Returns:
        list[ExitRequestRead]: Dwellers with a standing exit request.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    pending = await exit_request_service.list_pending(db_session, vault_id)
    return [_to_exit_request_read(dweller) for dweller in pending]


@router.post("/{dweller_id}/grant-exit", response_model=ExitDecisionResponse)
async def grant_exit_request(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExitDecisionResponse:
    """Let the dweller go: permanent death by exile, with no way back.

    Returns:
        ExitDecisionResponse: The exile outcome, including the epitaph.
    """
    dweller = await crud.dweller.get(db_session, dweller_id, include_deleted=True)
    vault = await get_user_vault_or_403(dweller.vault_id, user, db_session)
    dweller = await exit_request_service.grant_exit(db_session, vault, dweller_id)
    return ExitDecisionResponse(
        dweller_id=dweller.id,
        dweller_name=dweller.display_name,
        granted=True,
        happiness=dweller.happiness,
        epitaph=dweller.epitaph,
    )


@router.post("/{dweller_id}/refuse-exit", response_model=ExitDecisionResponse)
async def refuse_exit_request(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExitDecisionResponse:
    """Refuse the ask: the dweller takes a happiness hit and the request stands.

    Returns:
        ExitDecisionResponse: The refusal outcome and updated happiness.
    """
    dweller = await crud.dweller.get(db_session, dweller_id, include_deleted=True)
    vault = await get_user_vault_or_403(dweller.vault_id, user, db_session)
    dweller = await exit_request_service.refuse_exit(db_session, vault, dweller_id)
    return ExitDecisionResponse(
        dweller_id=dweller.id,
        dweller_name=dweller.display_name,
        granted=False,
        happiness=dweller.happiness,
    )
