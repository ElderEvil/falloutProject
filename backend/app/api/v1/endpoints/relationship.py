"""API endpoints for dweller relationship management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403, verify_dweller_access
from app.db.session import get_async_session
from app.models.dweller import Dweller
from app.schemas.relationship import (
    CompatibilityScore,
    RelationshipCreate,
    RelationshipRead,
)
from app.services.relationship_service import relationship_service

router = APIRouter()


@router.get("/vault/{vault_id}", response_model=list[RelationshipRead])
async def get_vault_relationships(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get all relationships in a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)

    from sqlmodel import select

    from app.models.dweller import Dweller
    from app.models.relationship import Relationship

    # Get all relationships where either dweller belongs to the vault
    query = (
        select(Relationship).join(Dweller, Relationship.dweller_1_id == Dweller.id).where(Dweller.vault_id == vault_id)
    )

    result = await db_session.execute(query)
    relationships = result.scalars().all()

    return relationships  # noqa: RET504


@router.get("/{relationship_id}", response_model=RelationshipRead)
async def get_relationship(
    relationship_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get a specific relationship."""
    from sqlmodel import select

    from app.models.relationship import Relationship

    query = select(Relationship).where(Relationship.id == relationship_id)
    result = await db_session.execute(query)
    relationship = result.scalars().first()

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Verify user has access to at least one dweller in the relationship
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
    relationship = await relationship_service.create_or_get_relationship(
        db_session,
        relationship_data.dweller_1_id,
        relationship_data.dweller_2_id,
    )

    return relationship  # noqa: RET504


@router.put("/{relationship_id}/romance", response_model=RelationshipRead)
async def initiate_romance(
    relationship_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Upgrade a relationship to romantic."""
    from sqlmodel import select

    from app.models.relationship import Relationship

    # Get relationship
    query = select(Relationship).where(Relationship.id == relationship_id)
    result = await db_session.execute(query)
    relationship = result.scalars().first()

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Verify access
    await verify_dweller_access(relationship.dweller_1_id, user, db_session)

    # Initiate romance
    try:
        updated_relationship = await relationship_service.initiate_romance(
            db_session,
            relationship.dweller_1_id,
            relationship.dweller_2_id,
        )
        return updated_relationship  # noqa: RET504, TRY300
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{relationship_id}/partner", response_model=RelationshipRead)
async def make_partners(
    relationship_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Make two dwellers partners (committed relationship)."""
    from sqlmodel import select

    from app.models.relationship import Relationship

    # Get relationship
    query = select(Relationship).where(Relationship.id == relationship_id)
    result = await db_session.execute(query)
    relationship = result.scalars().first()

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Verify access
    await verify_dweller_access(relationship.dweller_1_id, user, db_session)

    # Make partners
    try:
        updated_relationship = await relationship_service.make_partners(
            db_session,
            relationship.dweller_1_id,
            relationship.dweller_2_id,
        )
        return updated_relationship  # noqa: RET504, TRY300
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{relationship_id}")
async def break_up_relationship(
    relationship_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Break up a relationship."""
    from sqlmodel import select

    from app.models.relationship import Relationship

    # Get relationship
    query = select(Relationship).where(Relationship.id == relationship_id)
    result = await db_session.execute(query)
    relationship = result.scalars().first()

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Verify access
    await verify_dweller_access(relationship.dweller_1_id, user, db_session)

    # Break up
    try:
        await relationship_service.break_up(db_session, relationship_id)
        return {"message": "Relationship ended"}  # noqa: TRY300
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/vault/{vault_id}/quick-pair", response_model=RelationshipRead)
async def quick_pair_dwellers(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Quick pair two random compatible dwellers for testing.
    Creates a relationship, sets it to romantic, and makes them partners.
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    from sqlmodel import select

    from app.models.dweller import Dweller
    from app.schemas.common import GenderEnum

    # Get all adult dwellers in the vault without partners
    query = (
        select(Dweller)
        .where(Dweller.vault_id == vault_id)
        .where(Dweller.age_group == "adult")
        .where(Dweller.partner_id.is_(None))
    )

    result = await db_session.execute(query)
    available_dwellers = list(result.scalars().all())

    if len(available_dwellers) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 adult dwellers without partners")

    # Separate by gender
    males = [d for d in available_dwellers if d.gender == GenderEnum.MALE]
    females = [d for d in available_dwellers if d.gender == GenderEnum.FEMALE]

    if not males or not females:
        raise HTTPException(status_code=400, detail="Need at least one male and one female dweller")

    # Pick first available from each gender
    dweller_1 = males[0]
    dweller_2 = females[0]

    # Create relationship
    relationship = await relationship_service.create_or_get_relationship(
        db_session,
        dweller_1.id,
        dweller_2.id,
    )

    # Force set to high affinity (90) for quick pairing
    relationship.affinity = 90
    relationship.relationship_type = "romantic"
    await db_session.commit()
    await db_session.refresh(relationship)

    # Make them partners
    relationship = await relationship_service.make_partners(
        db_session,
        dweller_1.id,
        dweller_2.id,
    )

    return relationship  # noqa: RET504


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

    # Get dwellers
    from sqlmodel import select

    query_1 = select(Dweller).where(Dweller.id == dweller_1_id)
    query_2 = select(Dweller).where(Dweller.id == dweller_2_id)

    dweller_1 = (await db_session.execute(query_1)).scalars().first()
    dweller_2 = (await db_session.execute(query_2)).scalars().first()

    if not dweller_1 or not dweller_2:
        raise HTTPException(status_code=404, detail="Dweller not found")

    # Calculate compatibility
    from app.config.game_balance import (
        COMPATIBILITY_HAPPINESS_WEIGHT,
        COMPATIBILITY_LEVEL_WEIGHT,
        COMPATIBILITY_PROXIMITY_WEIGHT,
        COMPATIBILITY_SPECIAL_WEIGHT,
    )

    # SPECIAL similarity score
    special_attrs = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
    special_diff = sum(abs(getattr(dweller_1, attr, 0) - getattr(dweller_2, attr, 0)) for attr in special_attrs)
    max_special_diff = 7 * 10
    special_score = 1.0 - (special_diff / max_special_diff)

    # Happiness similarity
    happiness_diff = abs(dweller_1.happiness - dweller_2.happiness)
    happiness_score = 1.0 - (happiness_diff / 100.0)

    # Level similarity
    level_diff = abs(dweller_1.level - dweller_2.level)
    max_level_diff = 50
    level_score = 1.0 - (level_diff / max_level_diff)

    # Proximity (same room bonus)
    proximity_score = 1.0 if dweller_1.room_id == dweller_2.room_id and dweller_1.room_id is not None else 0.0

    # Weighted total
    compatibility = (
        special_score * COMPATIBILITY_SPECIAL_WEIGHT
        + happiness_score * COMPATIBILITY_HAPPINESS_WEIGHT
        + level_score * COMPATIBILITY_LEVEL_WEIGHT
        + proximity_score * COMPATIBILITY_PROXIMITY_WEIGHT
    )

    return CompatibilityScore(
        dweller_1_id=dweller_1_id,
        dweller_2_id=dweller_2_id,
        score=min(1.0, max(0.0, compatibility)),
        special_score=special_score,
        happiness_score=happiness_score,
        level_score=level_score,
        proximity_score=proximity_score,
    )
