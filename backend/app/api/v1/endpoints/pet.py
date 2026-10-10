"""Pet item endpoints."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_current_active_user
from app.db.session import get_async_session
from app.models.pet import Pet
from app.schemas.pet import PetRead
from app.services.pet_service import pet_service

router = APIRouter(prefix="/pets", tags=["Pet"], dependencies=[Depends(get_current_active_user)])


@router.get("/", response_model=list[PetRead])
async def read_pet_list(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> Sequence[Pet]:
    """Retrieve a paginated list of a vault's pets.

    Every pet lives in a vault's storage or on one of its dwellers, so the vault
    is required rather than optional: an unscoped list would enumerate other
    players' pets.

    Returns:
        List of pets.

    Raises:
        AccessDeniedException: If the user doesn't own the vault.
    """
    return await pet_service.list_pets(db_session, vault_id, user, skip, limit)


@router.get("/{pet_id}", response_model=PetRead)
async def read_pet(
    pet_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> Pet:
    """Retrieve a pet by ID.

    Returns:
        The requested pet.

    Raises:
        AccessDeniedException: If the user doesn't own the pet's vault.
    """
    return await pet_service.get_pet(db_session, pet_id, user)


@router.post("/{dweller_id}/equip/{pet_id}", response_model=PetRead)
async def equip_pet(
    dweller_id: UUID4,
    pet_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> Pet:
    """Equip a pet on a dweller.

    Returns:
        The equipped pet.

    Raises:
        AccessDeniedException: If the user owns neither the dweller nor the pet.
    """
    return await pet_service.equip(db_session, dweller_id, pet_id, user)


@router.post("/{pet_id}/unequip/", status_code=200, response_model=None)
async def unequip_pet(
    pet_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> None:
    """Unequip a pet from a dweller.

    Raises:
        AccessDeniedException: If the user doesn't own the pet's vault.
    """
    await pet_service.unequip(db_session, pet_id, user)
