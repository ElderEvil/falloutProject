"""Exploration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403, verify_exploration_access
from app.crud import exploration as crud_exploration
from app.db.session import get_async_session
from app.models.exploration import Exploration
from app.schemas.expedition import (
    AvailableSiteView,
    ExpeditionEnterRequest,
    ExpeditionResolveRequest,
    SiteRoomView,
)
from app.schemas.exploration import (
    ExpeditionDispatchRequest,
    ExplorationCompleteResponse,
    ExplorationProgress,
    ExplorationRead,
    ExplorationReadShort,
    ExplorationSendRequest,
    PendingOverflowRead,
)
from app.schemas.overflow import OverflowActionRequest, OverflowActionResponse
from app.services.exploration.expedition import expedition_service
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.utils.exceptions import ValidationException

router = APIRouter(prefix="/explorations", tags=["Exploration"])


@router.post("/send", response_model=ExplorationRead)
async def send_dweller_to_wasteland(
    request: ExplorationSendRequest,
    vault_id: Annotated[UUID4, Query()],
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Exploration:
    """Send a dweller to the wasteland for exploration.

    Returns:
        ExplorationRead: The created exploration.

    Raises:
        ValidationException: If the dweller cannot be sent.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    try:
        return await exploration_service.send_dweller(
            db_session,
            vault_id=vault_id,
            dweller_id=request.dweller_id,
            duration=request.duration,
            stimpaks=request.stimpaks,
            radaways=request.radaways,
        )
    except ValueError as e:
        raise ValidationException(str(e)) from e


@router.post("/dispatch", response_model=ExplorationRead)
async def dispatch_dweller(
    request: ExpeditionDispatchRequest,
    vault_id: Annotated[UUID4, Query()],
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Exploration:
    """Send a dweller to clear a specific map point.

    Returns:
        ExplorationRead: The created targeted exploration.

    Raises:
        ResourceNotFoundException: If the dweller or location is unknown to this vault.
        ValidationException: If the dweller cannot go or the point cannot be cleared.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await exploration_service.dispatch(
        db_session,
        vault_id=vault_id,
        dweller_id=request.dweller_id,
        location_id=request.location_id,
    )


@router.get("/vault/{vault_id}", response_model=list[ExplorationReadShort])
async def list_explorations_by_vault(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    active_only: bool = True,
) -> list[Exploration]:
    """List all explorations for a vault.

    Returns:
        list[ExplorationReadShort]: List of explorations.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud_exploration.get_by_vault(
        db_session,
        vault_id=vault_id,
        active_only=active_only,
    )


@router.get("/vault/{vault_id}/pending-overflow", response_model=list[PendingOverflowRead])
async def list_pending_overflow(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[PendingOverflowRead]:
    """List overflow loot that still needs a take or sell decision."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await rewards_service.get_pending_overflow(db_session, vault_id)


@router.get("/{exploration_id}", response_model=ExplorationRead)
async def get_exploration(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Exploration:
    """Get detailed information about an exploration.

    Returns:
        ExplorationRead: Exploration details.
    """
    await verify_exploration_access(exploration_id, user, db_session)
    return await crud_exploration.get(db_session, exploration_id)


@router.get("/{exploration_id}/progress", response_model=ExplorationProgress)
async def get_exploration_progress(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationProgress:
    """Get current progress of an exploration.

    Returns:
        ExplorationProgress: Current exploration progress.
    """
    await verify_exploration_access(exploration_id, user, db_session)
    return await exploration_service.get_exploration_progress(db_session, exploration_id)


@router.post("/{exploration_id}/recall", response_model=ExplorationCompleteResponse)
async def recall_dweller(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationCompleteResponse:
    """Recall a dweller early from exploration.

    Returns:
        ExplorationCompleteResponse: Exploration data and partial rewards.

    Raises:
        ValidationException: If the exploration cannot be recalled.
    """
    await verify_exploration_access(exploration_id, user, db_session)
    try:
        exploration, rewards = await exploration_service.recall_exploration_with_data(db_session, exploration_id)
        return ExplorationCompleteResponse(
            exploration=exploration,
            rewards_summary=rewards.model_dump() if rewards else None,
        )
    except ValueError as e:
        raise ValidationException(str(e)) from e


@router.post("/{exploration_id}/complete", response_model=ExplorationCompleteResponse)
async def complete_exploration(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationCompleteResponse:
    """Complete an exploration and collect rewards.

    Returns:
        ExplorationCompleteResponse: Exploration data and full rewards.

    Raises:
        ValidationException: If the exploration cannot be completed.
    """
    await verify_exploration_access(exploration_id, user, db_session)
    try:
        exploration, rewards = await exploration_service.complete_exploration_with_data(db_session, exploration_id)
        return ExplorationCompleteResponse(
            exploration=exploration,
            rewards_summary=rewards.model_dump() if rewards else None,
        )
    except ValueError as e:
        raise ValidationException(str(e)) from e


@router.post("/{exploration_id}/overflow/take", response_model=OverflowActionResponse)
async def take_overflow_item(
    exploration_id: UUID4,
    request: OverflowActionRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> OverflowActionResponse:
    """Store one unclaimed overflow item. 409 when storage is still full."""
    await verify_exploration_access(exploration_id, user, db_session)
    remaining = await rewards_service.take_unclaimed_item(db_session, exploration_id, request.index)
    return OverflowActionResponse(unclaimed_loot=remaining)


@router.post("/{exploration_id}/overflow/sell", response_model=OverflowActionResponse)
async def sell_overflow_item(
    exploration_id: UUID4,
    request: OverflowActionRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> OverflowActionResponse:
    """Sell one unclaimed overflow item for caps. Needs no storage space."""
    await verify_exploration_access(exploration_id, user, db_session)
    caps, remaining = await rewards_service.sell_unclaimed_item(db_session, exploration_id, request.index)
    return OverflowActionResponse(caps_granted=caps, unclaimed_loot=remaining)


@router.post("/{exploration_id}/generate_event", response_model=ExplorationRead)
async def generate_event(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Exploration:
    """Manually trigger event generation for an exploration (for testing/debugging).

    Returns:
        ExplorationRead: Updated exploration with generated event.

    Raises:
        ValidationException: If event generation fails.
    """
    await verify_exploration_access(exploration_id, user, db_session)
    try:
        return await exploration_service.process_event_for_exploration(db_session, exploration_id)
    except ValueError as e:
        raise ValidationException(str(e)) from e


@router.post("/{exploration_id}/site/enter", response_model=SiteRoomView)
async def enter_expedition_site(
    exploration_id: UUID4,
    request: ExpeditionEnterRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> SiteRoomView:
    """Enter an expedition site on an active exploration.

    Returns:
        SiteRoomView: The first room and its node prompt.
    """
    await verify_exploration_access(exploration_id, user, db_session)
    return await expedition_service.enter_run(db_session, exploration_id, request.site_id)


@router.get("/{exploration_id}/site/available", response_model=list[AvailableSiteView])
async def list_available_expedition_sites(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[AvailableSiteView]:
    """List expedition sites the dweller may currently enter (level + anti-farm gates)."""
    await verify_exploration_access(exploration_id, user, db_session)
    return await expedition_service.list_available_sites(db_session, exploration_id)


@router.get("/{exploration_id}/site", response_model=SiteRoomView | None)
async def get_expedition_site(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> SiteRoomView | None:
    """Get the open expedition run view, or null when there is none (reconnect-safe)."""
    await verify_exploration_access(exploration_id, user, db_session)
    return await expedition_service.current_view(db_session, exploration_id)


@router.post("/{exploration_id}/site/resolve", response_model=SiteRoomView)
async def resolve_expedition_node(
    exploration_id: UUID4,
    request: ExpeditionResolveRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> SiteRoomView:
    """Resolve the current site room node and advance.

    Returns:
        SiteRoomView: The next room view (or the finished run view).
    """
    await verify_exploration_access(exploration_id, user, db_session)
    return await expedition_service.resolve_node(db_session, exploration_id, request)


@router.post("/{exploration_id}/site/retreat", response_model=SiteRoomView)
async def retreat_expedition_site(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> SiteRoomView:
    """Abandon the expedition run at a room boundary; room loot is kept."""
    await verify_exploration_access(exploration_id, user, db_session)
    return await expedition_service.retreat_run(db_session, exploration_id)
