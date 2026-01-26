"""API endpoints for pregnancy management."""

import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.dweller import Dweller
from app.models.pregnancy import Pregnancy
from app.schemas.common import AgeGroupEnum, GenderEnum, PregnancyStatusEnum
from app.schemas.pregnancy import DeliveryResult, PregnancyRead
from app.services.breeding_service import breeding_service
from app.utils.exceptions import (
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    try:
        pregnancy, _ = await crud.pregnancy.get_with_vault_access(db_session, pregnancy_id, user)
    except ResourceNotFoundException as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc

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
    try:
        _, _mother = await crud.pregnancy.get_with_vault_access(db_session, pregnancy_id, user)
    except ResourceNotFoundException as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc

    # Attempt delivery
    try:
        child = await breeding_service.deliver_baby(db_session, pregnancy_id)

        # Note: notification is already sent by deliver_baby() in breeding_service

        return DeliveryResult(
            pregnancy_id=pregnancy_id,
            child_id=child.id,
            message=f"Baby {child.first_name} {child.last_name} has been born!",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# =============================================================================
# Debug Endpoints (Superuser only)
# =============================================================================


@router.post("/debug/force-conception", response_model=PregnancyRead)
async def force_conception(
    mother_id: UUID4,
    father_id: UUID4,
    user: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Force conception between two dwellers (debug only).

    Requires superuser access.
    """
    # Verify mother exists and is female adult
    mother_query = select(Dweller).where(Dweller.id == mother_id)
    mother = (await db_session.execute(mother_query)).scalars().first()

    if not mother:
        raise ResourceNotFoundException(Dweller, identifier=mother_id)

    if mother.gender != GenderEnum.FEMALE:
        raise ValidationException(detail="Mother must be female")

    if mother.age_group != AgeGroupEnum.ADULT:
        raise ValidationException(detail="Mother must be adult")

    # Verify father exists and is male adult
    father_query = select(Dweller).where(Dweller.id == father_id)
    father = (await db_session.execute(father_query)).scalars().first()

    if not father:
        raise ResourceNotFoundException(Dweller, identifier=father_id)

    if father.gender != GenderEnum.MALE:
        raise ValidationException(detail="Father must be male")

    if father.age_group != AgeGroupEnum.ADULT:
        raise ValidationException(detail="Father must be adult")

    # Check mother isn't already pregnant
    existing_query = select(Pregnancy).where(
        Pregnancy.mother_id == mother_id,
        Pregnancy.status == PregnancyStatusEnum.PREGNANT,
    )
    existing = (await db_session.execute(existing_query)).scalars().first()

    if existing:
        raise ResourceConflictException(detail="Mother is already pregnant")

    # Create pregnancy
    logger.info(
        "DEBUG force-conception triggered",
        extra={
            "mother_id": str(mother_id),
            "father_id": str(father_id),
            "triggered_by": user.username,
        },
    )

    pregnancy = await breeding_service.create_pregnancy(db_session, mother_id, father_id)

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


@router.post("/{pregnancy_id}/debug/accelerate", response_model=PregnancyRead)
async def accelerate_pregnancy(
    pregnancy_id: UUID4,
    user: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Accelerate pregnancy to be due immediately (superuser only)."""
    query = select(Pregnancy).where(Pregnancy.id == pregnancy_id)
    pregnancy = (await db_session.execute(query)).scalars().first()

    if not pregnancy:
        raise ResourceNotFoundException(Pregnancy, identifier=pregnancy_id)

    if pregnancy.status != PregnancyStatusEnum.PREGNANT:
        raise ValidationException(detail="Pregnancy is not active")

    # Set due_at to now (actually 1 second ago to ensure is_due returns True)
    old_due_at = pregnancy.due_at
    pregnancy.due_at = datetime.utcnow() - timedelta(seconds=1)
    pregnancy.updated_at = datetime.utcnow()

    await db_session.commit()
    await db_session.refresh(pregnancy)

    logger.info(
        "DEBUG pregnancy accelerated",
        extra={
            "pregnancy_id": str(pregnancy_id),
            "old_due_at": old_due_at.isoformat() if old_due_at else None,
            "new_due_at": pregnancy.due_at.isoformat(),
            "triggered_by": user.username,
        },
    )

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
