from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.crud.user_profile import profile_crud
from app.db.session import get_async_session
from app.schemas.user_profile import ProfileRead, ProfileUpdate

router = APIRouter()


@router.get("/me/profile", response_model=ProfileRead)
async def get_my_profile(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
):
    """Get current user's profile."""
    profile = await profile_crud.get_by_user_id(db_session, user.id)
    if not profile:
        # Auto-create profile if it doesn't exist
        profile = await profile_crud.create_for_user(db_session, user.id)
    return profile


@router.put("/me/profile", response_model=ProfileRead)
async def update_my_profile(
    *,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    profile_data: ProfileUpdate,
    user: CurrentActiveUser,
):
    """Update current user's profile."""
    profile = await profile_crud.get_by_user_id(db_session, user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return await profile_crud.update(db_session, id=profile.id, obj_in=profile_data)
