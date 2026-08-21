"""World-map service: register bio places, discoveries, and build map responses.

All ``register_*`` methods are best-effort — failures are logged at
``logger.exception`` level and NEVER raised to the caller.  This is
load-bearing because bio generation must not fail on map bookkeeping.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.core.game_config import game_config
from app.crud.wasteland_location import wasteland_location as wl_crud
from app.models.exploration import Exploration
from app.models.notification import NotificationPriority, NotificationType
from app.models.vault import Vault
from app.models.wasteland_location import (
    DwellerLocationRelationEnum,
    LocationTypeEnum,
    WastelandLocation,
)
from app.schemas.common import RarityEnum  # ruff: ignore[typing-only-first-party-import]
from app.schemas.wasteland_location import (
    DiscoveryRoutePoint,
    DiscoveryRouteRead,
    DwellerRef,
    VaultMapResponse,
    VaultMarkerRead,
    WastelandLocationWithDwellers,
)
from app.services.notification_service import notification_service
from app.utils.places import GENERIC_ORIGIN_SKIP, WORLD_SCALE, normalize_place_name, seeded_vault_specs

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller

logger = logging.getLogger(__name__)


class _MapDwellerLike(Protocol):
    """Structural protocol for dweller objects used by map registration methods."""

    id: UUID4
    vault_id: UUID4
    rarity: RarityEnum


@dataclass(frozen=True)
class _MapDwellerSnapshot:
    """Map registration values preserved across a session rollback."""

    id: UUID4
    vault_id: UUID4
    rarity: RarityEnum


class MapService:
    """Service layer for world-map bookkeeping."""

    # ------------------------------------------------------------------
    # best-effort helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _should_skip(name: str) -> bool:
        """Return True when *name* is generic / empty and should be dropped."""
        if not name:
            return True
        return normalize_place_name(name) in GENERIC_ORIGIN_SKIP

    # ------------------------------------------------------------------
    # home marker
    # ------------------------------------------------------------------

    async def ensure_home_marker(self, db_session: AsyncSession, vault: Vault) -> WastelandLocation:
        """Idempotent home-vault marker at (50.0, 50.0).

        Does NOT use ``get_or_create`` because the coordinates must be exact.
        """
        vault_name = f"Vault {vault.number:03}"
        normalized = normalize_place_name(vault_name)

        # Fast path — already exists
        existing = await wl_crud.get_by_normalized(db_session, vault.id, normalized)
        if existing is not None:
            return existing

        obj = WastelandLocation(
            name=vault_name,
            normalized_name=normalized,
            type=LocationTypeEnum.HOME_VAULT,
            coord_x=50.0,
            coord_y=50.0,
            description=f"Your vault — Vault {vault.number:03}",
            vault_id=vault.id,
        )
        db_session.add(obj)
        try:
            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()
            existing = await wl_crud.get_by_normalized(db_session, vault.id, normalized)
            if existing is not None:
                return existing
            raise
        else:
            await db_session.refresh(obj)
            return obj

    async def link_home_origin(self, db_session: AsyncSession, dweller: Dweller, vault: Vault) -> None:
        """Ensure the home marker exists and link *dweller* to it as ORIGIN — best-effort."""
        try:
            home = await self.ensure_home_marker(db_session, vault)
            await wl_crud.link_dweller(db_session, dweller.id, home.id, DwellerLocationRelationEnum.ORIGIN)
        except Exception:
            logger.exception("link_home_origin failed: dweller=%s vault=%s", dweller.id, vault.id)

    # ------------------------------------------------------------------
    # bio place registration
    # ------------------------------------------------------------------

    async def register_bio_places(
        self,
        db_session: AsyncSession,
        dweller: _MapDwellerLike,
        origin_place: str,
        visited_places: list[str],
        explicit_origin: str | None = None,
    ) -> bool:
        """Upsert bio origin + rarity-scaled visited location rows — best-effort.

        *effective origin* = *explicit_origin* when truthy, else *origin_place*.
        If the effective origin normalises to a generic skip token we suppress it.
        Every visited name (max 64 chars, skip-list applied) is upserted, capped
        at ``game_config.bio.max_visited`` for the dweller's rarity.

        A transient failure is retried once after rolling back the session. If
        both attempts fail, a durable notification makes the incomplete map
        registration visible without disrupting bio generation.

        Returns ``True`` when the registration succeeded (or nothing needed to be
        done), and ``False`` when it failed after the internal retry.
        """
        map_dweller = _MapDwellerSnapshot(
            id=dweller.id,
            vault_id=dweller.vault_id,
            rarity=dweller.rarity,
        )
        for attempt in range(2):
            try:
                await self._register_bio_places_once(
                    db_session,
                    map_dweller,
                    origin_place,
                    visited_places,
                    explicit_origin,
                )
            except Exception:
                await db_session.rollback()
                if attempt == 0:
                    logger.warning(
                        "register_bio_places retrying after failure: dweller=%s vault=%s origin=%r",
                        map_dweller.id,
                        map_dweller.vault_id,
                        origin_place,
                        exc_info=True,
                    )
                    continue

                logger.exception(
                    "register_bio_places failed after retry: dweller=%s vault=%s origin=%r",
                    map_dweller.id,
                    map_dweller.vault_id,
                    origin_place,
                )
            else:
                return True

        await self._notify_bio_registration_failure(db_session, map_dweller)
        return False

    async def _register_bio_places_once(
        self,
        db_session: AsyncSession,
        dweller: _MapDwellerLike,
        origin_place: str,
        visited_places: list[str],
        explicit_origin: str | None,
    ) -> None:
        """Register bio places once; callers handle best-effort recovery."""
        effective_origin = explicit_origin or origin_place

        # --- origin ---
        if not self._should_skip(effective_origin):
            origin_location = await wl_crud.get_or_create(
                db_session,
                vault_id=dweller.vault_id,
                name=effective_origin[:64],
                type=LocationTypeEnum.ORIGIN,
            )
            await wl_crud.link_dweller(db_session, dweller.id, origin_location.id, DwellerLocationRelationEnum.ORIGIN)

        # --- visited (rarity-scaled cap, de-dupe against origin, apply skip-list) ---
        origin_normalized = normalize_place_name(effective_origin)
        visited = 0
        max_visited = game_config.bio.max_visited(dweller.rarity.value)
        for raw_name in visited_places:
            if visited >= max_visited:
                break
            if not raw_name or self._should_skip(raw_name):
                continue
            name = raw_name[:64]
            n_name = normalize_place_name(name)
            # do not create a visited entry that collides with the origin row
            if n_name == origin_normalized:
                continue
            loc = await wl_crud.get_or_create(
                db_session,
                vault_id=dweller.vault_id,
                name=name,
                type=LocationTypeEnum.VISITED,
            )
            await wl_crud.link_dweller(db_session, dweller.id, loc.id, DwellerLocationRelationEnum.VISITED)
            visited += 1

    async def _notify_bio_registration_failure(
        self,
        db_session: AsyncSession,
        dweller: _MapDwellerLike,
    ) -> None:
        """Persist an actionable notification when map registration exhausts its retry."""
        try:
            vault = await db_session.get(Vault, dweller.vault_id)
            if vault is None:
                logger.error("Cannot notify map registration failure: vault=%s not found", dweller.vault_id)
                return

            await notification_service.create_and_send(
                db_session,
                user_id=vault.user_id,
                vault_id=vault.id,
                from_dweller_id=dweller.id,
                notification_type=NotificationType.MAP_REGISTRATION_FAILED,
                priority=NotificationPriority.HIGH,
                title="Map registration needs attention",
                message="A dweller's known locations could not be added to the map. Please try again later.",
            )
        except Exception:
            logger.exception(
                "Could not persist map registration failure notification: dweller=%s vault=%s",
                dweller.id,
                dweller.vault_id,
            )

    # ------------------------------------------------------------------
    # discovery registration
    # ------------------------------------------------------------------

    async def register_discovery(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        exploration_id: UUID4,
        location_name: str,
    ) -> WastelandLocation | None:
        """Upsert a DISCOVERY location row for an exploration — best-effort.

        Returns the location row (with id and coordinates) when successful, else None.
        """
        try:
            return await wl_crud.get_or_create(
                db_session,
                vault_id=vault_id,
                name=location_name[:64],
                type=LocationTypeEnum.DISCOVERY,
                exploration_id=exploration_id,
                commit=False,
            )
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

    async def _get_discovery_routes(
        self, db_session: AsyncSession, vault_id: UUID4
    ) -> list[DiscoveryRouteRead]:
        """Project discovery events into ordered map trails.

        A ``WastelandLocation`` is intentionally de-duplicated by place name,
        so it cannot faithfully represent repeated visits across expeditions.
        Event records are the journey history and therefore the route authority.
        Older events without the Journal coordinate fields are simply omitted.
        """
        result = await db_session.execute(select(Exploration).where(Exploration.vault_id == vault_id))
        routes: list[DiscoveryRouteRead] = []
        for exploration in result.scalars().all():
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
            if len(points) >= 2:
                points.sort(key=lambda point: point.timestamp)
                routes.append(DiscoveryRouteRead(exploration_id=exploration.id, points=points))
        return routes

    # ------------------------------------------------------------------
    # map assembly
    # ------------------------------------------------------------------

    async def get_location_detail(
        self,
        db_session: AsyncSession,
        vault: Vault,
        location_id: UUID4,
    ) -> WastelandLocationWithDwellers:
        """Return a single location with its linked dweller references."""
        location = await wl_crud.get_by_id(db_session, location_id)
        from app.utils.exceptions import ResourceNotFoundException

        if location is None or location.vault_id != vault.id:
            raise ResourceNotFoundException(WastelandLocation, identifier=location_id)

        refs_map = await wl_crud.get_dweller_refs(db_session, [location.id])
        refs = refs_map.get(location.id, [])

        dweller_refs = [
            DwellerRef(
                dweller_id=r["dweller_id"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                relation=r["relation"],
                is_unlocked=r.get("is_unlocked", False),
            )
            for r in refs
        ]

        return WastelandLocationWithDwellers(
            id=location.id,
            name=location.name,
            normalized_name=location.normalized_name,
            type=location.type,
            coord_x=round(location.coord_x * WORLD_SCALE, 1),
            coord_y=round(location.coord_y * WORLD_SCALE, 1),
            description=location.description,
            vault_id=location.vault_id,
            exploration_id=location.exploration_id,
            created_at=location.created_at,
            dwellers=dweller_refs,
            is_unlocked=any(r.is_unlocked for r in dweller_refs),
        )

    async def get_vault_map(
        self, db_session: AsyncSession, vault: Vault, *, unlocked_only: bool = False
    ) -> VaultMapResponse:
        """Build the full world-map payload for a vault.

        When *unlocked_only* is True, non-VAULT locations without any unlocked
        DwellerLocation link are excluded.  HOME_VAULT is always retained.
        """
        await self.ensure_home_marker(db_session, vault)

        # --- persisted locations ---
        rows = await wl_crud.get_by_vault(db_session, vault.id)
        location_ids = [r.id for r in rows]
        dweller_refs_map = await wl_crud.get_dweller_refs(db_session, location_ids)

        locations: list[WastelandLocationWithDwellers] = []
        for row in rows:
            refs = dweller_refs_map.get(row.id, [])
            dweller_refs = [
                DwellerRef(
                    dweller_id=r["dweller_id"],
                    first_name=r["first_name"],
                    last_name=r["last_name"],
                    relation=r["relation"],
                    is_unlocked=r.get("is_unlocked", False),
                )
                for r in refs
            ]
            location_unlocked = any(r.is_unlocked for r in dweller_refs)

            # When filtering, keep HOME_VAULT and unlocked locations; drop locked ones
            if unlocked_only and row.type != LocationTypeEnum.HOME_VAULT and not location_unlocked:
                continue

            locations.append(
                WastelandLocationWithDwellers(
                    id=row.id,
                    name=row.name,
                    normalized_name=row.normalized_name,
                    type=row.type,
                    coord_x=round(row.coord_x * WORLD_SCALE, 1),
                    coord_y=round(row.coord_y * WORLD_SCALE, 1),
                    description=row.description,
                    vault_id=row.vault_id,
                    exploration_id=row.exploration_id,
                    created_at=row.created_at,
                    dwellers=dweller_refs,
                    is_unlocked=location_unlocked,
                )
            )

        # --- computed vault markers ---
        specs = seeded_vault_specs(vault.number)
        vault_markers = [
            VaultMarkerRead(
                name=s.name,
                coord_x=round(s.coord_x * WORLD_SCALE, 1),
                coord_y=round(s.coord_y * WORLD_SCALE, 1),
                type="vault",
                description="Unexplored vault signal — raiding available in a future update.",
            )
            for s in specs
        ]

        discovery_routes = await self._get_discovery_routes(db_session, vault.id)
        return VaultMapResponse(
            locations=locations,
            vault_markers=vault_markers,
            discovery_routes=discovery_routes,
        )


# ------------------------------------------------------------------
# Module-level singleton — matches vault_service / quest_service etc.
# ------------------------------------------------------------------
map_service = MapService()
