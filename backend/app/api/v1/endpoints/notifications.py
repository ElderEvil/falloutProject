from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.crud.notification import notification as notification_crud
from app.db.session import get_async_session
from app.models.notification import NotificationCreate, NotificationRead
from app.schemas.responses import CountResponse, MarkReadResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=list[NotificationRead])
async def get_notifications(
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[NotificationRead]:
    """Get notifications for the current user"""
    return await notification_crud.get_user_notifications(
        db_session,
        user_id=user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=CountResponse)
async def get_unread_count(
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CountResponse:
    """Get count of unread notifications"""
    count = await notification_crud.get_unread_count(db_session, user_id=user.id)
    return CountResponse(count=count)


@router.post("/", response_model=NotificationRead)
async def create_notification(
    notification_data: NotificationCreate,
    user: CurrentActiveUser,  # noqa: ARG001
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> NotificationRead:
    """Create a new notification (admin/system use)"""
    return await notification_crud.create(db_session, obj_in=notification_data)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_as_read(
    notification_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> NotificationRead:
    """Mark a notification as read"""
    notification = await notification_crud.mark_as_read(db_session, notification_id=notification_id, user_id=user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post("/mark-all-read", response_model=MarkReadResponse)
async def mark_all_notifications_as_read(
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> MarkReadResponse:
    """Mark all notifications as read for the current user"""
    count = await notification_crud.mark_all_as_read(db_session, user_id=user.id)
    return MarkReadResponse(marked_read=count)


@router.delete("/{notification_id}", response_model=NotificationRead)
async def dismiss_notification(
    notification_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> NotificationRead:
    """Dismiss (soft delete) a notification"""
    notification = await notification_crud.dismiss(db_session, notification_id=notification_id, user_id=user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification
