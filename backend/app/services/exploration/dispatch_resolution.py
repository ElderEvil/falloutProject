"""Arrival resolution for targeted dispatch runs (issue 772, phases 2-3).

A dispatch run suppresses random events and resolves exactly once on arrival:
the party fights as a unit against the tier threat, a win rolls the place's
single shared haul, deaths trim the haul proportionally, then the return leg
carries it home.
"""

import logging
import random
from datetime import timedelta
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import NotificationPriority, NotificationType
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud import world_location as crud_world_location
from app.crud.team import team_crud
from app.crud.vault import vault as vault_crud
from app.models.exploration import Exploration
from app.models.world_location import VaultLocationState, WorldLocation
from app.schemas.exploration_event import LootItemSchema
from app.services.collectible_service import CollectibleAward, collectible_service
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.event_service import apply_exploration_damage, apply_loot_find
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration.loot_calculator import loot_calculator
from app.services.exploration.party_resolution import (
    apply_party_haul_loss,
    distribute_damage,
    resolve_party_combat,
)
from app.services.notification_service import notification_service
from app.utils.place_groups import effective_place_group
from app.utils.place_loot import loot_table
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


async def resolve_dispatch_arrival(db_session: AsyncSession, exploration_id: UUID, *, arrived: bool = False) -> None:
    """Resolve a targeted run's arrival: party fight, loot, clear state, then return leg."""
    exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
    if exploration is None or not exploration.is_dispatch_run() or not exploration.is_active():
        return
    if exploration.time_remaining_seconds() > 0 and not arrived:
        return

    target_location_id = exploration.target_location_id
    if target_location_id is None:
        return

    pair = await crud_world_location.get_state_with_location(db_session, exploration.vault_id, target_location_id)
    if pair is None:
        await exploration_coordinator.start_return(db_session, exploration_id, arrived=arrived)
        return
    location, state = pair
    group = effective_place_group(location.group_key, location.kind)
    if group is None:
        await exploration_coordinator.start_return(db_session, exploration_id, arrived=arrived)
        return
    if not group.get("clearable"):
        await _resolve_salvage(db_session, exploration, location, state, arrived)
        return
    now = utcnow()
    if not state.is_dispatchable(now):
        await exploration_coordinator.start_return(db_session, exploration_id, arrived=arrived)
        return

    # Dispatch always snapshots clear_tier; fall back to the escalation cap for legacy NULL rows.
    tier = (
        exploration.clear_tier
        if exploration.clear_tier is not None
        else min(state.clear_count, game_config.exploration.dispatch.escalation_cap)
    )
    difficulty = min(5, group["base_difficulty"] + tier)

    if exploration.team_id is not None:
        members = await team_crud.get_exploration_team_dwellers(db_session, exploration.id)
    else:
        anchor = await dweller_crud.get_with_equipment(db_session, exploration.dweller_id)
        members = [anchor] if anchor is not None and not anchor.is_dead else []
    if not members:
        await exploration_coordinator.start_return(db_session, exploration_id, arrived=arrived)
        return
    party_size = len(members)

    victory, total_damage = resolve_party_combat(members, difficulty)
    caps, loot_rolls = _roll_dispatch_loot(members, exploration, group, tier) if victory else (0, [])
    shares = distribute_damage(total_damage, party_size)
    lethal = tier >= game_config.exploration.dispatch.lethal_tier
    delete_held = party_size == 1
    for member, share in zip(members, shares, strict=True):
        await apply_exploration_damage(
            db_session,
            exploration,
            share,
            dweller_id=member.id,
            lethal=lethal,
            delete_held=delete_held,
        )

    deaths = 0
    survivors: list = []
    for member in members:
        fresh = await dweller_crud.get(db_session, member.id)
        if fresh is None or fresh.is_dead:
            deaths += 1
        else:
            survivors.append(fresh)

    collectible_payload = None
    if victory:
        exploration.total_caps_found += caps
        for item, item_type in loot_rolls:
            apply_loot_find(
                exploration,
                item_name=item.name,
                rarity=item.rarity,
                item_type=item_type,
                caps=0,
            )
        if deaths:
            apply_party_haul_loss(exploration, party_size, deaths)
        # Aggregate power can clear the victory threshold while the lethal tier
        # still wipes the party, so a wipe means nobody is left to hold the
        # clear: the point stays uncleared and the loot rolls are dropped below.
        if deaths < party_size:
            state.cleared_at = now
            state.reclear_available_at = now + timedelta(hours=group["reclear_hours"])
            state.clear_count += 1
            db_session.add(state)
            # 0 is a real outcome (a clear with no XP reward); NULL stays reserved for "no clear".
            exploration.location_xp = _location_xp(group, tier)

            vault = await vault_crud.get_or_none(db_session, exploration.vault_id)
            if vault is not None:
                await notification_service.create_and_send(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=vault.id,
                    notification_type=NotificationType.LOCATION_CLEARED,
                    priority=NotificationPriority.NORMAL,
                    title=f"{location.name} cleared",
                    message=f"{location.name} has been cleared. It will be ready to loot again soon.",
                    meta_data={
                        "location_id": str(state.location_id),
                        "location_name": location.name,
                    },
                    commit=False,
                )
            collectible_payload = await collectible_service.award_site_collectible(
                db_session, exploration=exploration, location=location, members=survivors
            )

    db_session.add(exploration)
    # Flush the loot/clear-state work before the return leg re-locks the run:
    # start_return's vault claim re-reads the exploration with populate_existing,
    # which would otherwise discard the staged haul.
    await db_session.flush()
    await exploration_coordinator.start_return(db_session, exploration_id, arrived=arrived)
    # start_return commits (persisting the LOCATION_CLEARED row and any parked
    # death notice); drain the deferred queue so they also go out live, then publish
    # the collectible event only after that commit.
    await notification_service.deliver_deferred_notifications(db_session)
    if collectible_payload is not None:
        await event_bus.emit(
            GameEvent.COLLECTIBLE_FOUND, exploration.vault_id, _collectible_payload(collectible_payload)
        )


def _roll_dispatch_loot(
    members: list, exploration: Exploration, group: dict, tier: int
) -> tuple[int, list[tuple[LootItemSchema, str]]]:
    """Roll the whole haul before combat writes stage, so a bad entry cannot leave a half-resolution."""
    table = loot_table(group["loot_table"])
    if table is None:
        return 0, []
    caps = random.randint(table["caps"]["min"], table["caps"]["max"])
    caps = int(caps * (1 + game_config.exploration.dispatch.reward_per_tier * tier)) * len(members)
    best_luck = max([member.luck for member in members] + [exploration.dweller_luck])
    rolls = [
        (
            loot_calculator.roll_item(
                best_luck,
                entry["type"],
                entry["rarity"],
                junk_types=entry.get("junk_types"),
                weapon_types=entry.get("weapon_types"),
            ),
            entry["type"],
        )
        for entry in table["items"]
    ]
    return caps, rolls


def _location_xp(group: dict, tier: int) -> int:
    """Location XP for a held clear, escalated with the tier like the caps payout."""
    base = group.get("xp_reward") or 0
    return int(base * (1 + game_config.exploration.dispatch.reward_per_tier * tier)) if base else 0


def _collectible_payload(award: CollectibleAward) -> dict:
    """Transport shape for the collectible event; the service keeps the domain object."""
    return {
        "collectible_key": award.collectible_key,
        "name": award.name,
        "stat": award.stat,
        "amount": award.amount,
        "dweller_id": str(award.dweller_id),
        "location_name": award.location_name,
    }


async def _resolve_salvage(
    db_session: AsyncSession,
    exploration: Exploration,
    location: WorldLocation,
    state: VaultLocationState,
    arrived: bool,
) -> None:
    """Resolve a one-dweller salvage at an inert site: the bobblehead, a small find, a spent site.

    Runs under the vault lock acquired by the caller; the claim and ``searched_at`` are staged and
    ``start_return`` remains the transaction owner. No combat: salvaging never damages the dweller.
    """
    if not game_config.features.collectibles or state.searched_at is not None:
        await exploration_coordinator.start_return(db_session, exploration.id, arrived=arrived)
        return
    if exploration.team_id is not None:
        members = list(await team_crud.get_exploration_team_dwellers(db_session, exploration.id))
    else:
        anchor = await dweller_crud.get_with_equipment(db_session, exploration.dweller_id)
        members = [anchor] if anchor is not None else []
    if len(members) != 1 or members[0].is_dead:
        await exploration_coordinator.start_return(db_session, exploration.id, arrived=arrived)
        return

    state.searched_at = utcnow()
    db_session.add(state)
    payload = await collectible_service.award_site_collectible(
        db_session, exploration=exploration, location=location, members=members, action="salvage"
    )
    if payload is not None:
        exploration.total_caps_found += random.randint(5, 20)
    db_session.add(exploration)
    await db_session.flush()
    await exploration_coordinator.start_return(db_session, exploration.id, arrived=arrived)
    await notification_service.deliver_deferred_notifications(db_session)
    if payload is not None:
        await event_bus.emit(GameEvent.COLLECTIBLE_FOUND, exploration.vault_id, _collectible_payload(payload))
