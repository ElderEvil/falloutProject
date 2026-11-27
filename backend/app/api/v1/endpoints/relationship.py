"""Relationship endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentActiveUser,
    DBSession,
    get_accessible_relationship,
    get_user_vault_or_403,
    verify_dweller_access,
)
from app.models.relationship import Relationship
from app.schemas.relationship import (
    CompatibilityScore,
    RelationshipCreate,
    RelationshipRead,
    VaultRelationshipRead,
)
from app.schemas.responses import BreedStatsResponse, RelationshipActionResponse
from app.services.game_loop_service import game_loop_service
from app.services.relationship_service import relationship_service

router = APIRouter(prefix="/relationships", tags=["Relationship"])


@router.get("/vault/{vault_id}", response_model=list[VaultRelationshipRead])
async def get_vault_relationships(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> list[VaultRelationshipRead]:
    """Get all relationships in a vault.

    Returns:
        List of relationships in the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await relationship_service.get_vault_relationships_with_progress(db_session, vault_id)


@router.get("/{relationship_id}", response_model=RelationshipRead)
async def get_relationship(
    relationship: Annotated[Relationship, Depends(get_accessible_relationship)],
) -> Relationship:
    """Retrieve a relationship by ID.

    Returns:
        The requested relationship.

    Raises:
        HTTPException: 404 if relationship not found.
        HTTPException: 403 if user doesn't have access.
    """
    return relationship


@router.post("/", response_model=RelationshipRead)
async def create_relationship(
    relationship_data: RelationshipCreate,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Relationship:
    """Create or get a relationship between two dwellers.

    Returns:
        The created or existing relationship.
    """
    # Verify access to both dwellers
    await verify_dweller_access(relationship_data.dweller_1_id, user, db_session)
    await verify_dweller_access(relationship_data.dweller_2_id, user, db_session)

    # Create or get existing relationship
    return await relationship_service.get_or_create_relationship(
        db_session, relationship_data.dweller_1_id, relationship_data.dweller_2_id
    )


@router.put("/{relationship_id}/romance", response_model=RelationshipRead)
async def initiate_romance(
    relationship: Annotated[Relationship, Depends(get_accessible_relationship)],
    db_session: DBSession,
) -> Relationship:
    """Initiate romance between two dwellers in a relationship.

    Returns:
        The updated relationship.

    Raises:
        HTTPException: 404 if relationship not found.
        HTTPException: 400 if romance cannot be initiated.
        HTTPException: 403 if user doesn't have access.
    """
    return await relationship_service.initiate_romance(
        db_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
    )


@router.put("/{relationship_id}/partner", response_model=RelationshipRead)
async def make_partners(
    relationship: Annotated[Relationship, Depends(get_accessible_relationship)],
    db_session: DBSession,
) -> Relationship:
    """Make two dwellers in a relationship romantic partners.

    Returns:
        The updated relationship.

    Raises:
        HTTPException: 404 if relationship not found.
        HTTPException: 400 if partnership cannot be established.
        HTTPException: 403 if user doesn't have access.
    """
    return await relationship_service.make_partners(
        db_session,
        relationship.dweller_1_id,
        relationship.dweller_2_id,
    )


@router.put("/{relationship_id}/marry", response_model=RelationshipRead)
async def marry(
    relationship: Annotated[Relationship, Depends(get_accessible_relationship)],
    db_session: DBSession,
) -> Relationship:
    """Marry two partners in a relationship.

    Returns:
        The updated relationship.

    Raises:
        HTTPException: 404 if relationship not found.
        HTTPException: 400 if marriage cannot be performed.
        HTTPException: 403 if user doesn't have access.
    """
    # marry raises ValidationException (HTTP 400) for invalid marriage attempts.
    return await relationship_service.marry(db_session, relationship.id)


@router.delete("/{relationship_id}", response_model=RelationshipActionResponse)
async def break_up_relationship(
    relationship: Annotated[Relationship, Depends(get_accessible_relationship)],
    db_session: DBSession,
) -> RelationshipActionResponse:
    """Break up a relationship between two dwellers.

    Returns:
        Confirmation message.

    Raises:
        HTTPException: 404 if relationship not found.
        HTTPException: 400 if breakup cannot be performed.
        HTTPException: 403 if user doesn't have access.
    """
    await relationship_service.break_up(db_session, relationship.id)
    return RelationshipActionResponse(message="Relationship ended")


@router.get("/compatibility/{dweller_1_id}/{dweller_2_id}", response_model=CompatibilityScore)
async def calculate_compatibility(
    dweller_1_id: UUID,
    dweller_2_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> CompatibilityScore:
    """Calculate compatibility score between two dwellers.

    Returns:
        Compatibility score between the two dwellers.
    """
    # Verify access to both dwellers
    await verify_dweller_access(dweller_1_id, user, db_session)
    await verify_dweller_access(dweller_2_id, user, db_session)

    # Use service for compatibility calculation
    # calculate_compatibility_score raises ResourceNotFoundException when dweller not found
    # (via dweller_crud.get), which is an HTTPException 404 - let it propagate directly
    return await relationship_service.calculate_compatibility_score(db_session, dweller_1_id, dweller_2_id)


@router.post("/vault/{vault_id}/process", response_model=BreedStatsResponse)
async def process_vault_breeding(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> BreedStatsResponse:
    """Process breeding and relationships for a vault.

    Returns:
        Breeding processing statistics.
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    result = await game_loop_service.process_vault_breeding(db_session, vault_id)

    return BreedStatsResponse(
        message="Breeding and relationships processed successfully",
        stats=result,
    )
