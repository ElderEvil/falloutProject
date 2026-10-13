"""World-map service: register bio places, discoveries, and build map responses.

Thin facade over the ``app.services.map`` domain package: ``MapService`` keeps
the public surface — and the ``map_service`` singleton — stable for its diverse
callers, delegating each entry point to the role-named collaborators
(``bio_registration``, ``discovery``, and ``reads``).

All ``register_*`` methods are best-effort — failures are logged at
``logger.exception`` level and NEVER raised to the caller.  This is
load-bearing because bio generation must not fail on map bookkeeping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]

from app.services.map import bio_registration, discovery, reads

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller
    from app.models.vault import Vault
    from app.models.world_location import WorldLocation
    from app.schemas.wasteland_location import VaultMapResponse, WastelandLocationWithDwellers
    from app.services.map.bio_registration import _MapDwellerLike, _MapDwellerSnapshot


class MapService:
    """Service layer for world-map bookkeeping."""

    async def ensure_home_marker(self, db_session: AsyncSession, vault: Vault) -> WorldLocation:
        """Home-vault marker at the vault's slot placement + per-vault HOME_VAULT state."""
        return await bio_registration.ensure_home_marker(db_session, vault)

    async def link_home_origin(self, db_session: AsyncSession, dweller: Dweller, vault: Vault) -> None:
        """Ensure the home marker exists and link *dweller* to it as ORIGIN — best-effort."""
        await bio_registration.link_home_origin(db_session, dweller, vault)

    async def register_bio_places(
        self,
        db_session: AsyncSession,
        dweller: _MapDwellerLike,
        origin_place: str,
        visited_places: list[str],
        explicit_origin: str | None = None,
        *,
        commit: bool = True,
    ) -> bool:
        """Upsert bio origin + rarity-scaled visited location rows — best-effort.

        Returns ``True`` when the registration succeeded (or nothing needed to be
        done), and ``False`` when it failed after the internal retry.
        """
        return await bio_registration.register_bio_places(
            db_session, dweller, origin_place, visited_places, explicit_origin, commit=commit
        )

    async def notify_bio_registration_failure(
        self,
        db_session: AsyncSession,
        dweller: _MapDwellerLike | _MapDwellerSnapshot,
    ) -> None:
        """Persist an actionable notification when map registration exhausts its retry."""
        await bio_registration.notify_bio_registration_failure(db_session, dweller)

    async def register_discovery(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        exploration_id: UUID4,
        dweller_id: UUID4,
        location_name: str,
    ) -> WorldLocation | None:
        """Upsert a DISCOVERY state and unlock the place for the exploring dweller (best-effort)."""
        return await discovery.register_discovery(db_session, vault_id, exploration_id, dweller_id, location_name)

    async def register_spatial_discovery(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        exploration_id: UUID4,
        dweller_id: UUID4,
        location_name: str,
        position: tuple[float, float],
        world_version: int | None,
    ) -> WorldLocation | None:
        """Register a discovery found while moving: nearby place, else journey-scoped."""
        return await discovery.register_spatial_discovery(
            db_session, vault_id, exploration_id, dweller_id, location_name, position, world_version
        )

    async def sweep_reclears(self, db_session: AsyncSession) -> int:
        """Null elapsed reclear windows and notify owners the point is ready again."""
        return await discovery.sweep_reclears(db_session)

    async def get_location_detail(
        self,
        db_session: AsyncSession,
        vault: Vault,
        location_id: UUID4,
    ) -> WastelandLocationWithDwellers:
        """Return a single location with its linked dweller references."""
        return await reads.get_location_detail(db_session, vault, location_id)

    async def get_vault_map(
        self, db_session: AsyncSession, vault: Vault, *, unlocked_only: bool = False
    ) -> VaultMapResponse:
        """Build the full world-map payload for a vault.

        When *unlocked_only* is True, non-VAULT locations without any unlocked
        DwellerLocation link are excluded.  HOME_VAULT is always retained.
        """
        return await reads.get_vault_map(db_session, vault, unlocked_only=unlocked_only)


# ------------------------------------------------------------------
# Module-level singleton — matches vault_service / quest_service etc.
# ------------------------------------------------------------------
map_service = MapService()
