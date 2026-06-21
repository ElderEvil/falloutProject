import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.dweller import Dweller
from app.schemas.pregnancy import DeliveryResult, PregnancyRead
from app.services.breeding_service import breeding_service
from app.utils.exceptions import ResourceNotFoundException, ValidationException

router = APIRouter(prefix="/pregnancies", tags=["Pregnancy"])
logger = logging.getLogger(__name__)


@router.get("/vault/{vault_id}", response_model=list[PregnancyRead])
async def get_vault_pregnancies(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[PregnancyRead]:
    """Get all active pregnancies in a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)

    pregnancies = await breeding_service.get_active_pregnancies(
        db_session,
        vault_id,
    )

    return [PregnancyRead.model_validate(p) for p in pregnancies]


@router.get("/{pregnancy_id}", response_model=PregnancyRead)
async def get_pregnancy(
    pregnancy_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> PregnancyRead:
    """Get a specific pregnancy."""
    try:
        pregnancy, _ = await crud.pregnancy.get_with_vault_access(db_session, pregnancy_id, user)
    except ResourceNotFoundException as exc:
        raise HTTPException(status_code=404, detail=exc.detail) from exc

    return PregnancyRead.model_validate(pregnancy)


@router.post("/{pregnancy_id}/deliver", response_model=DeliveryResult)
async def deliver_baby(
    pregnancy_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> DeliveryResult:
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
) -> PregnancyRead:
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
        error_msg = str(e).lower()
        if "not found" in error_msg:
            identifier = mother_id if "mother" in error_msg else father_id
            raise ResourceNotFoundException(model=Dweller, identifier=identifier) from e
        raise ValidationException(detail=str(e)) from e

    return PregnancyRead.model_validate(pregnancy)


@router.post("/{pregnancy_id}/debug/accelerate", response_model=PregnancyRead)
async def accelerate_pregnancy(
    pregnancy_id: UUID4,
    user: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> PregnancyRead:
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

    return PregnancyRead.model_validate(pregnancy)
