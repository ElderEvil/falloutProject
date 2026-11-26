"""Map reads: location detail and full world-map assembly.

Public operations are called through ``MapService`` in ``app.services.map_service``;
the description/clear-state/group-key helpers shape persisted rows into the wire
contract, and site markers project the expedition catalog onto the map.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from app.core.enums import LocationTypeEnum
from app.core.game_config import game_config
from app.crud.exploration import exploration as exploration_crud
from app.crud.vault_slot import vault_slot as vault_slot_crud
from app.crud.world_location import world_location as wl_crud
from app.models.exploration import IN_PROGRESS_STATUSES
from app.models.world_location import VaultLocationState, WorldLocation
from app.schemas.wasteland_location import (
    DwellerRef,
    ExpeditionSiteMarkerRead,
    LocationCaravanStateRead,
    LocationClearStateRead,
    LocationLootEntryRead,
    PlaceGroupRead,
    PlayerVaultMarkerRead,
    VaultMapResponse,
    VaultMarkerRead,
    WastelandLocationWithDwellers,
)
from app.services.catalog_service import load_expedition_sites
from app.services.collectible_service import collectible_service
from app.services.exploration.site_offers import (
    SiteBlockState,
    journey_offer_context,
    site_block_state,
    site_is_offered,
    uses_single_scene,
)
from app.services.map import bio_registration, discovery
from app.utils.collectibles import collectible_for_location, salvage_ready
from app.utils.place_groups import effective_place_group, load_place_groups, location_xp_for, trade_entry, trade_terms
from app.utils.place_loot import loot_table
from app.utils.places import WORLD_SCALE
from app.utils.time import utcnow
from app.utils.vault_slots import slot_coords

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.vault import Vault
    from app.schemas.expedition import SiteDefinition


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
    now = utcnow()
    tier = min(state.clear_count, game_config.exploration.dispatch.escalation_cap)
    return LocationClearStateRead(
        clearable=True,
        cleared=state.is_cleared(now),
        clear_count=state.clear_count,
        tier=tier,
        time_remaining_seconds=state.time_remaining_seconds(now),
        loot_table=group.get("loot_table"),
        xp_per_survivor=location_xp_for(group, tier),
        loot_preview=_loot_preview(group.get("loot_table")),
    )


def _loot_preview(loot_key: str | None) -> list[LocationLootEntryRead]:
    """Declared rolls for the map preview; ``signature`` marks the table's identity entry."""
    table = loot_table(loot_key) if loot_key else None
    if table is None:
        return []
    return [
        LocationLootEntryRead(
            item_type=entry["type"],
            rarity=entry["rarity"],
            junk_types=entry.get("junk_types") or [],
            weapon_types=entry.get("weapon_types") or [],
            signature=index == 0,
        )
        for index, entry in enumerate(table["items"])
    ]


def _caravan_for(
    state: VaultLocationState,
    location: WorldLocation,
    *,
    unlocked: bool,
    busy: bool,
    has_slot: bool,
    now: datetime,
) -> LocationCaravanStateRead | None:
    """The caravan offer for a tradeable place, with the single reason it is refused (None = ready).

    Shopfront for the service's own rule: a refusal here is the message ``dispatch`` would raise, so the
    map never dangles a button the write path rejects.
    """
    entry = trade_entry(location.name)
    fee, cooldown_hours = trade_terms(effective_place_group(location.group_key, location.kind))
    if entry is None or fee == 0:
        return None
    remaining = 0
    if state.caravan_available_at is not None:
        remaining = max(0, int((state.caravan_available_at - now).total_seconds()))
    refusal = (
        "Not known to the vault"
        if not unlocked
        else "A party is already on its way"
        if busy
        else "No caravan ready yet"
        if remaining
        else "Vault has no map placement"
        if not has_slot
        else None
    )
    return LocationCaravanStateRead(
        material=entry["material"],
        band=entry["band"],
        caps_cost=fee,
        party_cap=game_config.exploration.dispatch.max_party_size,
        cooldown_remaining_seconds=remaining,
        cooldown_total_seconds=cooldown_hours * 3600,
        refusal_reason=refusal,
    )


def _action_for(
    state: VaultLocationState,
    location: WorldLocation,
    *,
    unlocked: bool,
    busy: bool = False,
    caravan: LocationCaravanStateRead | None = None,
) -> Literal["clear", "salvage", "trade", "none"]:
    """What the map offers at this point: clear, a salvage, trade, or nothing.

    A place the vault has not unlocked, or one with a party already en route, offers nothing:
    the dispatch service refuses both, so advertising an action here would only produce a dead-end
    button. Salvage implies the place is not clearable and the catalog binds a salvage collectible to
    it; ``salvage_ready`` is the same rule the write path applies, so a searched place — magazine
    included — offers nothing ever again. The collectible feature flag keeps inert places inert
    while the content is switched off.
    """
    if caravan is not None and caravan.refusal_reason is None:
        return "trade"
    if not unlocked:
        return "none"
    if busy:
        return "none"
    group = effective_place_group(location.group_key, location.kind)
    if group is not None and group.get("clearable"):
        return "clear"
    entry = collectible_for_location(location.name, action="salvage")
    if game_config.features.collectibles and entry is not None and salvage_ready(searched_at=state.searched_at):
        return "salvage"
    return "none"


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
    location_id: UUID,
) -> WastelandLocationWithDwellers:
    """Return a single location with its linked dweller references."""
    from app.utils.exceptions import ensure_found

    pair = await wl_crud.get_state_with_location(db_session, vault.id, location_id)
    pair = ensure_found(pair, WorldLocation, identifier=location_id)
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
    location_unlocked = any(r.is_unlocked for r in dweller_refs)
    busy = await exploration_crud.has_active_dispatch_to(db_session, vault_id=vault.id, location_id=state.location_id)
    caravan = _caravan_for(
        state,
        location,
        unlocked=location_unlocked,
        busy=await exploration_crud.has_unfinished_dispatch_to(
            db_session, vault_id=vault.id, location_id=state.location_id
        ),
        has_slot=await vault_slot_crud.get_by_vault(db_session, vault.id) is not None,
        now=utcnow(),
    )

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
        is_unlocked=location_unlocked,
        dispatch_in_progress=busy,
        clear_state=_clear_state_for(state, location),
        caravan=caravan,
        action=_action_for(state, location, unlocked=location_unlocked, busy=busy, caravan=caravan),
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
    dispatch_targets = await exploration_crud.get_active_dispatch_location_ids(db_session, vault_id=vault.id)
    unfinished_targets = await exploration_crud.get_active_dispatch_location_ids(
        db_session, vault_id=vault.id, statuses=IN_PROGRESS_STATUSES
    )
    has_slot = await vault_slot_crud.get_by_vault(db_session, vault.id) is not None
    now = utcnow()

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
        busy = state.location_id in dispatch_targets

        # When filtering, keep HOME_VAULT and unlocked locations; drop locked ones
        if unlocked_only and state.type != LocationTypeEnum.HOME_VAULT and not location_unlocked:
            continue

        caravan = _caravan_for(
            state,
            location,
            unlocked=location_unlocked,
            busy=state.location_id in unfinished_targets,
            has_slot=has_slot,
            now=now,
        )
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
                dispatch_in_progress=busy,
                clear_state=_clear_state_for(state, location),
                caravan=caravan,
                action=_action_for(state, location, unlocked=location_unlocked, busy=busy, caravan=caravan),
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
    # Dark feature: the catalog and its progress are not advertised while collectibles are off.
    collectible_sets = (
        await collectible_service.set_progress(db_session, vault_id=vault.id)
        if game_config.features.collectibles
        else []
    )

    return VaultMapResponse(
        locations=locations,
        vault_markers=vault_markers,
        player_vaults=player_vaults,
        discovery_routes=discovery_routes,
        place_groups=[PlaceGroupRead(**group) for group in load_place_groups()],
        expedition_sites=expedition_sites,
        collectible_sets=collectible_sets,
    )


def _site_marker(
    site: SiteDefinition,
    block: SiteBlockState,
    exploration_id: UUID | None = None,
    *,
    spatial: bool = False,
) -> ExpeditionSiteMarkerRead:
    """Project one catalog site plus its journey/anti-farm block state onto the wire."""
    return ExpeditionSiteMarkerRead(
        id=site.id,
        name=site.name,
        flavor=site.flavor,
        coord_x=round(site.coord_x * WORLD_SCALE, 1),
        coord_y=round(site.coord_y * WORLD_SCALE, 1),
        min_dweller_level=site.min_dweller_level,
        room_total=1 if uses_single_scene(site, spatial=spatial) else len(site.rooms),
        cleared=block.cleared,
        cooldown_remaining_seconds=block.cooldown_remaining_seconds,
        block_reason=block.reason,
        exploration_id=exploration_id,
    )


async def _expedition_site_markers(db_session: AsyncSession, vault: Vault) -> list[ExpeditionSiteMarkerRead]:
    """Journey-offered sites across in-progress spatial runs, else the legacy catalog.

    Spatial journeys contribute sites near their traveled trail (consumed ones drop out) with their exploration
    id for routing; legacy journeys keep the catalog with anti-farm cooldowns. Temporary markers expire with the
    journey — no journey, no markers.
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
                if site.scenario_only or site.id in offered_ids or not site_is_offered(site, context):
                    continue
                markers.append(_site_marker(site, SiteBlockState(), exploration.id, spatial=True))
                offered_ids.add(site.id)
        return markers
    if not explorations:
        return []
    return [
        _site_marker(site, await site_block_state(db_session, vault.id, site.id))
        for site in load_expedition_sites()
        if not site.scenario_only
    ]
