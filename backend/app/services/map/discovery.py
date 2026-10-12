"""Map discovery: journey places, spatial discovery, routes, and the reclear sweep.

Public operations are called through ``MapService`` in ``app.services.map_service``.
The discovery registrations are best-effort: a failed flush rolls back and is
logged rather than raised, so the surrounding exploration event can continue
without a map link.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum
from app.crud.exploration import exploration as exploration_crud
from app.crud.vault import vault as vault_crud
from app.crud.world_location import world_location as wl_crud
from app.crud.world_snapshot import world_snapshot as world_snapshot_crud
from app.models.notification import NotificationPriority, NotificationType
from app.schemas.wasteland_location import DiscoveryRoutePoint, DiscoveryRouteRead
from app.services.notification_service import notification_service
from app.services.world_generation_service import WORLD_ID
from app.utils import world_terrain
from app.utils.places import WORLD_SCALE

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.world_location import WorldLocation

logger = logging.getLogger(__name__)


async def _link_discovery(
    db_session: AsyncSession,
    vault_id: UUID4,
    exploration_id: UUID4,
    dweller_id: UUID4,
    location: WorldLocation,
) -> None:
    """Create the vault state + dweller link for a resolved discovery place."""
    await wl_crud.get_or_create_state(
        db_session,
        vault_id,
        location.id,
        LocationTypeEnum.DISCOVERY,
        exploration_id=exploration_id,
        commit=False,
    )
    await wl_crud.link_dweller(
        db_session,
        dweller_id,
        location.id,
        DwellerLocationRelationEnum.VISITED,
        is_unlocked=True,
        commit=False,
    )


async def register_discovery(
    db_session: AsyncSession,
    vault_id: UUID4,
    exploration_id: UUID4,
    dweller_id: UUID4,
    location_name: str,
) -> WorldLocation | None:
    """Upsert a DISCOVERY state and unlock the place for the exploring dweller (best-effort)."""
    try:
        location = await wl_crud.get_or_create_location(
            db_session,
            location_name[:64],
            commit=False,
        )
        await _link_discovery(db_session, vault_id, exploration_id, dweller_id, location)
    except Exception:
        # A failed flush leaves SQLAlchemy's transaction unusable. This
        # registration is best-effort and runs before the event mutation,
        # so reset it and let the discovery event continue without a link.
        await db_session.rollback()
        logger.exception(
            "register_discovery failed: vault=%s exploration=%s name=%r",
            vault_id,
            exploration_id,
            location_name,
        )
        return None
    else:
        return location


async def _create_journey_place(
    db_session: AsyncSession,
    exploration_id: UUID4,
    location_name: str,
    coord_x: float,
    coord_y: float,
) -> WorldLocation:
    """A new spatial row keyed to journey and position, not to the name.

    Identity is a pure function of the inputs, so concurrent discoveries
    cannot race on allocation: same position merges (one place), different
    positions never compete for one row.
    """
    key = f"{exploration_id}:{coord_x:.1f},{coord_y:.1f}"
    return await wl_crud.get_or_create_location(
        db_session,
        location_name[:64],
        coords=(coord_x, coord_y),
        normalized_name=key,
        commit=False,
    )


async def register_spatial_discovery(
    db_session: AsyncSession,
    vault_id: UUID4,
    exploration_id: UUID4,
    dweller_id: UUID4,
    location_name: str,
    position: tuple[float, float],
    world_version: int | None,
) -> WorldLocation | None:
    """Register a discovery found while moving: nearby place, else journey-scoped.

    An existing PLACE row within the fog's site radius is claimed where it
    stands (its coordinates never move); otherwise a new place is created
    at the explorer's position snapped to the nearest land tile, keyed to
    the journey so distant same-name rows can never hijack it.
    Best-effort like ``register_discovery``.
    """
    try:
        coord_x, coord_y = position
        snapshot = (
            await world_snapshot_crud.get_version(db_session, world_id=WORLD_ID, generator_version=world_version)
            if world_version is not None
            else None
        )
        if snapshot is not None:
            radius = world_terrain.reveal_radius_registry(snapshot, world_terrain.SITE_REVEAL_TILES)
            nearby = await wl_crud.get_nearest_within(db_session, coord_x, coord_y, radius)
            if nearby is not None:
                location = nearby
            else:
                coord_x, coord_y = world_terrain.nearest_land(snapshot, coord_x, coord_y)
                location = await _create_journey_place(db_session, exploration_id, location_name, coord_x, coord_y)
        else:
            location = await _create_journey_place(db_session, exploration_id, location_name, coord_x, coord_y)
        await _link_discovery(db_session, vault_id, exploration_id, dweller_id, location)
    except Exception:
        await db_session.rollback()
        logger.exception(
            "register_spatial_discovery failed: vault=%s exploration=%s name=%r",
            vault_id,
            exploration_id,
            location_name,
        )
        return None
    else:
        return location


async def get_discovery_routes(db_session: AsyncSession, vault_id: UUID4) -> list[DiscoveryRouteRead]:
    """Project a journey into ordered map coordinates.

    Spatial runs use their persisted movement trail: the durable path
    segments the fog corridor follows. Legacy runs use discovery events —
    a ``WastelandLocation`` is de-duplicated by place name, so it cannot
    faithfully represent repeated visits, and event records are the journey
    authority there. Older events without coordinate fields are omitted.
    """
    explorations = await exploration_crud.get_by_vault(db_session, vault_id=vault_id)
    routes: list[DiscoveryRouteRead] = []
    for exploration in explorations:
        points = (
            _movement_route_points(exploration)
            if exploration.heading_degrees is not None
            else _discovery_route_points(exploration)
        )
        if len(points) >= 2:
            points.sort(key=lambda point: point.timestamp)
            routes.append(
                DiscoveryRouteRead(
                    exploration_id=exploration.id,
                    points=points,
                    is_active=exploration.is_in_progress(),
                )
            )
    return routes


def _movement_route_points(exploration) -> list[DiscoveryRoutePoint]:
    """A spatial run's traveled path, scaled into wire coordinates."""
    points: list[DiscoveryRoutePoint] = []
    for step in exploration.trail or []:
        coord_x = step.get("x")
        coord_y = step.get("y")
        timestamp = step.get("t")
        if coord_x is None or coord_y is None or not isinstance(timestamp, str):
            continue
        points.append(
            DiscoveryRoutePoint(
                coord_x=round(float(coord_x) * WORLD_SCALE, 1),
                coord_y=round(float(coord_y) * WORLD_SCALE, 1),
                timestamp=timestamp,
            )
        )
    return points


def _discovery_route_points(exploration) -> list[DiscoveryRoutePoint]:
    """A legacy run's discovery events, scaled into wire coordinates."""
    points: list[DiscoveryRoutePoint] = []
    for event in exploration.events:
        if event.get("type") != "discovery":
            continue
        location_id = event.get("location_id")
        coord_x = event.get("coord_x")
        coord_y = event.get("coord_y")
        timestamp = event.get("timestamp")
        if location_id is None or coord_x is None or coord_y is None or not isinstance(timestamp, str):
            continue
        points.append(
            DiscoveryRoutePoint(
                location_id=location_id,
                coord_x=round(float(coord_x) * WORLD_SCALE, 1),
                coord_y=round(float(coord_y) * WORLD_SCALE, 1),
                timestamp=timestamp,
            )
        )
    return points


async def sweep_reclears(db_session: AsyncSession) -> int:
    """Null elapsed reclear windows and notify owners the point is ready again.

    The null is the idempotency guard: a second sweep finds nothing. A vault
    whose owner row is missing is skipped without aborting the sweep.
    """
    pairs = await wl_crud.get_elapsed_reclears(db_session, datetime.utcnow())
    for location, state in pairs:
        state.reclear_available_at = None
        db_session.add(state)
        vault = await vault_crud.get_or_none(db_session, state.vault_id)
        if vault is None:
            logger.error("Cannot notify reclear ready: vault=%s not found", state.vault_id)
            continue
        await notification_service.create_and_send(
            db_session,
            user_id=vault.user_id,
            vault_id=vault.id,
            notification_type=NotificationType.LOCATION_READY,
            priority=NotificationPriority.NORMAL,
            title=f"{location.name} ready",
            message=f"{location.name} is ready to be cleared again.",
            meta_data={
                "location_id": str(state.location_id),
                "location_name": location.name,
            },
            commit=False,
        )
    await db_session.commit()
    await notification_service.deliver_deferred_notifications(db_session)
    return len(pairs)
