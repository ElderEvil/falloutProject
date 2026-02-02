import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403
from app.db.session import get_async_session
from app.schemas.pregnancy import DeliveryResult, PregnancyRead
from app.services.breeding_service import breeding_service
from app.utils.exceptions import ResourceNotFoundException

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
    logger.info(
        "DEBUG force-conception triggered",
        extra={
            "mother_id": str(mother_id),
            "father_id": str(father_id),
            "triggered_by": user.username,
        },
    )

    try:
        pregnancy = await breeding_service.force_conception(db_session, mother_id, father_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

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
    try:
        pregnancy = await breeding_service.accelerate_pregnancy(db_session, pregnancy_id)
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    logger.info(
        "DEBUG pregnancy accelerated",
        extra={
            "pregnancy_id": str(pregnancy_id),
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
