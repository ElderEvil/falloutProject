"""Notification endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.crud.notification import notification as notification_crud
from app.db.session import get_async_session
from app.models.notification import Notification, NotificationRead
from app.schemas.responses import CountResponse, MarkReadResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=list[NotificationRead])
async def get_notifications(
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    """Get notifications for the current user.

    Returns:
        List of notifications for the user.
    """
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
    """Get count of unread notifications.

    Returns:
        Count of unread notifications.
    """
    count = await notification_crud.get_unread_count(db_session, user_id=user.id)
    return CountResponse(count=count)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
async def mark_notification_as_read(
    notification_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Notification:
    """Mark a notification as read.

    Returns:
        The updated notification.

    Raises:
        HTTPException: 404 if notification not found.
    """
    notification = await notification_crud.mark_as_read(db_session, notification_id=notification_id, user_id=user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post("/mark-all-read", response_model=MarkReadResponse)
async def mark_all_notifications_as_read(
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> MarkReadResponse:
    """Mark all notifications as read for the current user.

    Returns:
        Response with count of notifications marked as read.
    """
    count = await notification_crud.mark_all_as_read(db_session, user_id=user.id)
    return MarkReadResponse(marked_read=count)


@router.delete("/{notification_id}", response_model=NotificationRead)
async def dismiss_notification(
    notification_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Notification:
    """Dismiss (soft delete) a notification.

    Returns:
        The dismissed notification.

    Raises:
        HTTPException: 404 if notification not found.
    """
    notification = await notification_crud.dismiss(db_session, notification_id=notification_id, user_id=user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification
