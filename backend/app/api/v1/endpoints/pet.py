"""Pet item endpoints."""

from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import CurrentActiveUser, DBSession, PetPaginationParams, get_current_active_user
from app.models.pet import Pet
from app.schemas.pet import PetRead
from app.schemas.responses import NULL_BODY_RESPONSES
from app.services.pet_service import pet_service

router = APIRouter(prefix="/pets", tags=["Pet"], dependencies=[Depends(get_current_active_user)])


@router.get("/", response_model=list[PetRead])
async def read_pet_list(
    vault_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
    pagination: PetPaginationParams,
) -> Sequence[Pet]:
    """Retrieve a paginated list of a vault's pets.

    Every pet lives in a vault's storage or on one of its dwellers, so the vault
    is required rather than optional: an unscoped list would enumerate other
    players' pets.
    """
    return await pet_service.list_pets(db_session, vault_id, user, pagination.skip, pagination.limit)


@router.get("/{pet_id}", response_model=PetRead)
async def read_pet(
    pet_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> Pet:
    """Retrieve a pet by ID."""
    return await pet_service.get_pet(db_session, pet_id, user)


@router.post("/{dweller_id}/equip/{pet_id}", response_model=PetRead)
async def equip_pet(
    dweller_id: UUID,
    pet_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> Pet:
    """Equip a pet on a dweller."""
    return await pet_service.equip(db_session, dweller_id, pet_id, user)


@router.post("/{pet_id}/unequip/", status_code=200, response_model=None, responses=NULL_BODY_RESPONSES)
async def unequip_pet(
    pet_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
) -> None:
    """Unequip a pet from a dweller."""
    await pet_service.unequip(db_session, pet_id, user)
