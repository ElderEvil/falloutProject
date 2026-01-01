"""API endpoints for pregnancy management."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.dweller import Dweller
from app.models.pregnancy import Pregnancy
from app.schemas.pregnancy import DeliveryResult, PregnancyRead
from app.services.breeding_service import breeding_service

router = APIRouter()


@router.get("/vault/{vault_id}", response_model=list[PregnancyRead])
async def get_vault_pregnancies(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get all active pregnancies in a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)

    pregnancies = await breeding_service.get_active_pregnancies(
        db_session,
        vault_id,
    )

    # Convert to read schema with computed properties
    return [
        PregnancyRead(
            id=p.id,
            mother_id=p.mother_id,
            father_id=p.father_id,
            conceived_at=p.conceived_at,
            due_at=p.due_at,
            status=p.status,
            progress_percentage=p.progress_percentage,
            time_remaining_seconds=p.time_remaining_seconds,
            is_due=p.is_due,
        )
        for p in pregnancies
    ]


@router.get("/{pregnancy_id}", response_model=PregnancyRead)
async def get_pregnancy(
    pregnancy_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get a specific pregnancy."""
    query = select(Pregnancy).where(Pregnancy.id == pregnancy_id)
    result = await db_session.execute(query)
    pregnancy = result.scalars().first()

    if not pregnancy:
        raise HTTPException(status_code=404, detail="Pregnancy not found")

    # Get mother to verify vault access
    mother_query = select(Dweller).where(Dweller.id == pregnancy.mother_id)
    mother = (await db_session.execute(mother_query)).scalars().first()

    if not mother:
        raise HTTPException(status_code=404, detail="Mother dweller not found")

    # Verify user has access to the vault
    await get_user_vault_or_403(mother.vault_id, user, db_session)

    return PregnancyRead(
        id=pregnancy.id,
        mother_id=pregnancy.mother_id,
        father_id=pregnancy.father_id,
        conceived_at=pregnancy.conceived_at,
        due_at=pregnancy.due_at,
        status=pregnancy.status,
        progress_percentage=pregnancy.progress_percentage,
        time_remaining_seconds=pregnancy.time_remaining_seconds,
        is_due=pregnancy.is_due,
    )


@router.post("/{pregnancy_id}/deliver", response_model=DeliveryResult)
async def deliver_baby(
    pregnancy_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Manually trigger delivery of a baby (must be due)."""
    # Get pregnancy
    query = select(Pregnancy).where(Pregnancy.id == pregnancy_id)
    result = await db_session.execute(query)
    pregnancy = result.scalars().first()

    if not pregnancy:
        raise HTTPException(status_code=404, detail="Pregnancy not found")

    # Get mother to verify vault access
    mother_query = select(Dweller).where(Dweller.id == pregnancy.mother_id)
    mother = (await db_session.execute(mother_query)).scalars().first()

    if not mother:
        raise HTTPException(status_code=404, detail="Mother dweller not found")

    # Verify user has access to the vault
    await get_user_vault_or_403(mother.vault_id, user, db_session)

    # Attempt delivery
    try:
        child = await breeding_service.deliver_baby(db_session, pregnancy_id)
        return DeliveryResult(
            pregnancy_id=pregnancy_id,
            child_id=child.id,
            message=f"Baby {child.first_name} {child.last_name} has been born!",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
