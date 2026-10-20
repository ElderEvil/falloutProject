"""Map reads: location detail and full world-map assembly.

Public operations are called through ``MapService`` in ``app.services.map_service``;
the description/clear-state/group-key helpers shape persisted rows into the wire
contract, and site markers project the expedition catalog onto the map.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]

from app.core.enums import LocationTypeEnum
from app.core.game_config import game_config
from app.crud.exploration import exploration as exploration_crud
from app.crud.vault_slot import vault_slot as vault_slot_crud
from app.crud.world_location import world_location as wl_crud
from app.models.world_location import VaultLocationState, WorldLocation
from app.schemas.wasteland_location import (
    DwellerRef,
    ExpeditionSiteMarkerRead,
    LocationClearStateRead,
    PlaceGroupRead,
    PlayerVaultMarkerRead,
    VaultMapResponse,
    VaultMarkerRead,
    WastelandLocationWithDwellers,
)
from app.services.catalog_service import load_expedition_sites
from app.services.exploration.expedition import (
    SiteBlockState,
    journey_offer_context,
    site_block_state,
    site_is_offered,
)
from app.services.map import bio_registration, discovery
from app.utils.place_groups import effective_place_group, load_place_groups
from app.utils.places import WORLD_SCALE
from app.utils.vault_slots import slot_coords

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.vault import Vault


def _description_for(state: VaultLocationState, location: WorldLocation) -> str | None:
    """Canonical lore, then per-vault description, then the archetype's shared lore."""
    if location.description:
        return location.description
    if state.description:
        return state.description
    group = effective_place_group(location.group_key, location.kind)
    return group.get("description") if group else None


def _clear_state_for(state: VaultLocationState, location: WorldLocation) -> LocationClearStateRead | None:
    """Derive the read-only clear state for a map point, or None when not clearable.

    Availability is computed from ``now`` and never persisted; non-clearable
    groups and ungrouped points carry no clear state on the wire.
    """
    group = effective_place_group(location.group_key, location.kind)
    if group is None or not group.get("clearable"):
        return None
    now = datetime.utcnow()
    return LocationClearStateRead(
        clearable=True,
        cleared=state.is_cleared(now),
        clear_count=state.clear_count,
        tier=min(state.clear_count, game_config.exploration.dispatch.escalation_cap),
        time_remaining_seconds=state.time_remaining_seconds(now),
        loot_table=group.get("loot_table"),
    )


def _group_key_for(location: WorldLocation) -> str | None:
    """Effective archetype key for the wire.

    An ungrouped PLACE resolves to the default ``wasteland_site`` archetype
    (when emergent sites are enabled), so the client renders a real site icon
    instead of falling back to a bare marker-type glyph.
    """
    group = effective_place_group(location.group_key, location.kind)
    return group["key"] if group else None


async def get_location_detail(
    db_session: AsyncSession,
    vault: Vault,
    location_id: UUID4,
) -> WastelandLocationWithDwellers:
    """Return a single location with its linked dweller references."""
    from app.utils.exceptions import ResourceNotFoundException

    pair = await wl_crud.get_state_with_location(db_session, vault.id, location_id)
    if pair is None:
        raise ResourceNotFoundException(WorldLocation, identifier=location_id)
    location, state = pair

    refs_map = await wl_crud.get_dweller_refs(db_session, vault.id, [location.id])
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
        id=state.location_id,
        name=location.name,
        normalized_name=location.normalized_name,
        type=state.type,
        coord_x=round(location.coord_x * WORLD_SCALE, 1),
        coord_y=round(location.coord_y * WORLD_SCALE, 1),
        description=_description_for(state, location),
        group_key=_group_key_for(location),
        vault_id=vault.id,
        exploration_id=state.exploration_id,
        created_at=state.created_at,
        dwellers=dweller_refs,
        is_unlocked=any(r.is_unlocked for r in dweller_refs),
        clear_state=_clear_state_for(state, location),
    )


async def get_vault_map(db_session: AsyncSession, vault: Vault, *, unlocked_only: bool = False) -> VaultMapResponse:
    """Build the full world-map payload for a vault.

    When *unlocked_only* is True, non-VAULT locations without any unlocked
    DwellerLocation link are excluded.  HOME_VAULT is always retained.
    """
    await bio_registration.ensure_home_marker(db_session, vault)

    # --- persisted locations ---
    pairs = await wl_crud.get_states_by_vault(db_session, vault.id)
    location_ids = [state.location_id for _, state in pairs]
    dweller_refs_map = await wl_crud.get_dweller_refs(db_session, vault.id, location_ids)

    locations: list[WastelandLocationWithDwellers] = []
    for location, state in pairs:
        refs = dweller_refs_map.get(state.location_id, [])
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
        if unlocked_only and state.type != LocationTypeEnum.HOME_VAULT and not location_unlocked:
            continue

        locations.append(
            WastelandLocationWithDwellers(
                id=state.location_id,
                name=location.name,
                normalized_name=location.normalized_name,
                type=state.type,
                coord_x=round(location.coord_x * WORLD_SCALE, 1),
                coord_y=round(location.coord_y * WORLD_SCALE, 1),
                description=_description_for(state, location),
                group_key=_group_key_for(location),
                vault_id=vault.id,
                exploration_id=state.exploration_id,
                created_at=state.created_at,
                dwellers=dweller_refs,
                is_unlocked=location_unlocked,
                clear_state=_clear_state_for(state, location),
            )
        )

    # --- seeded NPC vault signals (persisted registry rows) ---
    seeded_vaults = await wl_crud.get_seeded_vaults(db_session)
    vault_markers = [
        VaultMarkerRead(
            name=row.name,
            coord_x=round(row.coord_x * WORLD_SCALE, 1),
            coord_y=round(row.coord_y * WORLD_SCALE, 1),
            type="vault",
            description=row.description or "An unclassified vault signal. No contact established.",
        )
        for row in seeded_vaults
    ]

    discovery_routes = await discovery.get_discovery_routes(db_session, vault.id)

    # --- real player vaults on the shared atlas (discoverable by all users) ---
    slot_rows = await vault_slot_crud.list_markers(db_session)
    player_vaults = [
        PlayerVaultMarkerRead(
            vault_id=slot_vault_id,
            number=number,
            coord_x=round(slot_coords(slot_index)[0] * WORLD_SCALE, 1),
            coord_y=round(slot_coords(slot_index)[1] * WORLD_SCALE, 1),
            is_mine=slot_user_id == vault.user_id,
        )
        for slot_index, slot_vault_id, number, slot_user_id in slot_rows
    ]

    expedition_sites = await _expedition_site_markers(db_session, vault)

    return VaultMapResponse(
        locations=locations,
        vault_markers=vault_markers,
        player_vaults=player_vaults,
        discovery_routes=discovery_routes,
        place_groups=[PlaceGroupRead(**group) for group in load_place_groups()],
        expedition_sites=expedition_sites,
    )


def _site_marker(site, block: SiteBlockState, exploration_id=None) -> ExpeditionSiteMarkerRead:
    """Project one catalog site plus its journey/anti-farm block state onto the wire."""
    return ExpeditionSiteMarkerRead(
        id=site.id,
        name=site.name,
        flavor=site.flavor,
        coord_x=round(site.coord_x * WORLD_SCALE, 1),
        coord_y=round(site.coord_y * WORLD_SCALE, 1),
        min_dweller_level=site.min_dweller_level,
        room_total=len(site.rooms),
        cleared=block.cleared,
        cooldown_remaining_seconds=block.cooldown_remaining_seconds,
        block_reason=block.reason,
        exploration_id=exploration_id,
    )


async def _expedition_site_markers(db_session: AsyncSession, vault: Vault) -> list[ExpeditionSiteMarkerRead]:
    """Journey-offered sites across in-progress spatial runs, else the legacy catalog.

    Every in-progress spatial journey contributes the sites near its traveled
    trail (consumed ones drop out), carrying its exploration id so the client can
    route entry to the right journey. Legacy journeys keep the catalog with
    anti-farm cooldowns. With no in-progress journey there are no temporary
    markers at all — they expire with the journey rather than reverting to a
    permanent catalog.
    """
    explorations = await exploration_crud.get_by_vault(db_session, vault_id=vault.id, active_only=True)
    spatial = [exploration for exploration in explorations if exploration.heading_degrees is not None]
    if spatial:
        markers: list[ExpeditionSiteMarkerRead] = []
        offered_ids: set[str] = set()
        for exploration in spatial:
            context = await journey_offer_context(db_session, exploration)
            if context is None:
                continue
            for site in load_expedition_sites():
                if site.id in offered_ids or not site_is_offered(site, context):
                    continue
                markers.append(_site_marker(site, SiteBlockState(), exploration.id))
                offered_ids.add(site.id)
        return markers
    if not explorations:
        return []
    return [
        _site_marker(site, await site_block_state(db_session, vault.id, site.id)) for site in load_expedition_sites()
    ]
