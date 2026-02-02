from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403, verify_dweller_access
from app.crud.relationship import relationship_crud
from app.db.session import get_async_session
from app.schemas.relationship import (
    CompatibilityScore,
    RelationshipCreate,
    RelationshipRead,
)
from app.services.relationship_service import relationship_service
from app.utils.exceptions import ResourceNotFoundException

router = APIRouter()


@router.get("/vault/{vault_id}", response_model=list[RelationshipRead])
async def get_vault_relationships(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await get_user_vault_or_403(vault_id, user, db_session)
    return await relationship_crud.get_by_vault(db_session, vault_id)


@router.get("/{relationship_id}", response_model=RelationshipRead)
async def get_relationship(
    relationship_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    try:
        relationship = await relationship_crud.get(db_session, relationship_id)
    except ResourceNotFoundException:
        raise HTTPException(status_code=404, detail="Relationship not found") from None

    await verify_dweller_access(relationship.dweller_1_id, user, db_session)
    return relationship


@router.post("/", response_model=RelationshipRead)
async def create_relationship(
    relationship_data: RelationshipCreate,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Create or get a relationship between two dwellers."""
    # Verify access to both dwellers
    await verify_dweller_access(relationship_data.dweller_1_id, user, db_session)
    await verify_dweller_access(relationship_data.dweller_2_id, user, db_session)

    # Create or get existing relationship
    return await relationship_service.get_or_create_relationship(
        db_session, relationship_data.dweller_1_id, relationship_data.dweller_2_id
    )


@router.put("/{relationship_id}/romance", response_model=RelationshipRead)
async def initiate_romance(
    relationship_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    try:
        relationship = await relationship_crud.get(db_session, relationship_id)
    except ResourceNotFoundException:
        raise HTTPException(status_code=404, detail="Relationship not found") from None

    await verify_dweller_access(relationship.dweller_1_id, user, db_session)

    try:
        return await relationship_service.initiate_romance(
            db_session,
            relationship.dweller_1_id,
            relationship.dweller_2_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{relationship_id}/partner", response_model=RelationshipRead)
async def make_partners(
    relationship_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    try:
        relationship = await relationship_crud.get(db_session, relationship_id)
    except ResourceNotFoundException:
        raise HTTPException(status_code=404, detail="Relationship not found") from None

    await verify_dweller_access(relationship.dweller_1_id, user, db_session)

    try:
        return await relationship_service.make_partners(
            db_session,
            relationship.dweller_1_id,
            relationship.dweller_2_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{relationship_id}")
async def break_up_relationship(
    relationship_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    try:
        relationship = await relationship_crud.get(db_session, relationship_id)
    except ResourceNotFoundException:
        raise HTTPException(status_code=404, detail="Relationship not found") from None

    await verify_dweller_access(relationship.dweller_1_id, user, db_session)

    try:
        await relationship_service.break_up(db_session, relationship_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"message": "Relationship ended"}


@router.post("/vault/{vault_id}/quick-pair", response_model=RelationshipRead)
async def quick_pair_dwellers(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    ☢️ Irradiated Cupid ☢️

    Instantly pairs two random compatible dwellers for testing/fun.
    - Finds one male and one female without partners
    - Creates a high-affinity relationship (90%)
    - Makes them romantic partners
    - Moves them to a private living quarters (kicks out any third wheels!)
    - Ready to breed immediately with 90% conception chance per tick
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    # Use service for quick pairing logic
    try:
        relationship = await relationship_service.quick_pair_dwellers(db_session, vault_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return relationship


@router.get("/compatibility/{dweller_1_id}/{dweller_2_id}", response_model=CompatibilityScore)
async def calculate_compatibility(
    dweller_1_id: UUID4,
    dweller_2_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Calculate compatibility score between two dwellers."""
    # Verify access to both dwellers
    await verify_dweller_access(dweller_1_id, user, db_session)
    await verify_dweller_access(dweller_2_id, user, db_session)

    # Use service for compatibility calculation
    # calculate_compatibility_score raises ResourceNotFoundException when dweller not found
    # (via dweller_crud.get), which is an HTTPException 404 - let it propagate directly
    return await relationship_service.calculate_compatibility_score(db_session, dweller_1_id, dweller_2_id)


@router.post("/vault/{vault_id}/process")
async def process_vault_breeding(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await get_user_vault_or_403(vault_id, user, db_session)

    from app.services.game_loop import game_loop_service

    result = await game_loop_service._process_breeding(db_session, vault_id)

    return {
        "message": "Breeding and relationships processed successfully",
        "stats": result,
    }
