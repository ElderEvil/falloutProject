from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.schemas.common import RadioModeEnum
from app.schemas.radio import ManualRecruitRequest, RadioStatsRead, RecruitmentResponse
from app.services.radio_service import radio_service
from app.utils.exceptions import ValidationException

router = APIRouter()


@router.get("/vault/{vault_id}/stats", response_model=RadioStatsRead)
async def get_radio_stats(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get recruitment statistics for a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)

    stats = await radio_service.get_recruitment_stats(db_session, vault_id)
    return RadioStatsRead(**stats)


@router.post("/vault/{vault_id}/recruit", response_model=RecruitmentResponse)
async def manual_recruit_dweller(
    vault_id: UUID4,
    recruit_request: ManualRecruitRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Manually recruit a dweller for caps."""
    await get_user_vault_or_403(vault_id, user, db_session)

    try:
        from app.core.game_config import game_config

        dweller = await radio_service.manual_recruit(
            db_session,
            vault_id,
            override=recruit_request.override,
        )

        # Note: notification is already sent by recruit_dweller() in radio_service

        return RecruitmentResponse(
            dweller=dweller,  # type: ignore  # noqa: PGH003
            message=f"{dweller.first_name} {dweller.last_name} has joined your vault!",
            caps_spent=game_config.radio.manual_recruitment_cost,
        )
    except ValueError as e:
        raise ValidationException(detail=str(e)) from e


@router.put("/vault/{vault_id}/mode")
async def set_radio_mode(
    vault_id: UUID4,
    mode: RadioModeEnum,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Set radio mode (recruitment or happiness)."""
    vault = await get_user_vault_or_403(vault_id, user, db_session)

    # Store the enum value as a string
    vault.radio_mode = mode.value
    await db_session.commit()

    return {"message": f"Radio mode set to {mode.value}", "radio_mode": mode.value}


@router.put("/vault/{vault_id}/room/{room_id}/speedup")
async def set_radio_speedup(
    vault_id: UUID4,
    room_id: UUID4,
    speedup: float,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await get_user_vault_or_403(vault_id, user, db_session)

    if not 1.0 <= speedup <= 10.0:
        raise ValidationException(detail="Speedup must be between 1.0 and 10.0")

    try:
        room = await radio_service.set_room_speedup(db_session, vault_id, room_id, speedup)
    except ValueError as e:
        raise ValidationException(detail=str(e)) from e

    return {
        "message": f"Radio room speedup set to {speedup}x",
        "room_id": str(room.id),
        "speedup": room.speedup_multiplier,
    }
