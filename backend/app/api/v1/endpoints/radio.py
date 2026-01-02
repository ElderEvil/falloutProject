"""API endpoints for radio recruitment system."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import RadioModeEnum
from app.schemas.radio import ManualRecruitRequest, RadioStatsRead, RecruitmentResponse
from app.services.radio_service import radio_service

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
        dweller = await radio_service.manual_recruit(
            db_session,
            vault_id,
            override=recruit_request.override,
        )

        # Get updated vault to check caps spent
        vault_query = select(Vault).where(Vault.id == vault_id)
        vault = (await db_session.execute(vault_query)).scalars().first()  # noqa: F841

        from app.config.game_balance import MANUAL_RECRUITMENT_COST

        return RecruitmentResponse(
            dweller=dweller,  # type: ignore  # noqa: PGH003
            message=f"{dweller.first_name} {dweller.last_name} has joined your vault!",
            caps_spent=MANUAL_RECRUITMENT_COST,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
    """Set speedup multiplier for a specific radio room."""
    await get_user_vault_or_403(vault_id, user, db_session)

    # Validate speedup range
    if not 1.0 <= speedup <= 10.0:
        raise HTTPException(status_code=400, detail="Speedup must be between 1.0 and 10.0")

    # Get the room
    room_query = select(Room).where(Room.id == room_id).where(Room.vault_id == vault_id)
    room = (await db_session.execute(room_query)).scalars().first()

    if not room:
        raise HTTPException(status_code=404, detail="Radio room not found")

    # Check if it's a radio room
    if "radio" not in room.name.lower():
        raise HTTPException(status_code=400, detail="Room is not a radio room")

    room.speedup_multiplier = speedup
    await db_session.commit()

    return {
        "message": f"Radio room speedup set to {speedup}x",
        "room_id": str(room_id),
        "speedup": speedup,
    }
