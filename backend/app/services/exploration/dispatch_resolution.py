"""Arrival resolution for targeted dispatch runs (issue 772, phase 2).

A dispatch run suppresses random events and resolves exactly once on arrival:
fight the tier-scaled enemy, roll the place's loot table on a win, mark the
point cleared, then start the return leg so the haul travels home.
"""

import logging
import random
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud import world_location as crud_world_location
from app.crud.vault import vault as vault_crud
from app.models.notification import NotificationPriority, NotificationType
from app.services.exploration.combat_calculator import combat_calculator
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.event_service import apply_exploration_damage, apply_loot_find
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration.loot_calculator import loot_calculator
from app.services.notification_service import notification_service
from app.utils.place_groups import get_place_group
from app.utils.place_loot import loot_table

logger = logging.getLogger(__name__)


async def resolve_dispatch_arrival(db_session: AsyncSession, exploration_id: UUID4) -> None:
    """Resolve a targeted run's arrival: fight, loot, clear state, then return leg."""
    exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
    if exploration is None or not exploration.is_dispatch_run() or not exploration.is_active():
        return
    if exploration.time_remaining_seconds() > 0:
        return

    target_location_id = exploration.target_location_id
    if target_location_id is None:
        return

    pair = await crud_world_location.get_state_with_location(db_session, exploration.vault_id, target_location_id)
    if pair is None:
        await exploration_coordinator.start_return(db_session, exploration_id)
        return
    location, state = pair
    group = get_place_group(location.group_key)
    if group is None or not group.get("clearable"):
        await exploration_coordinator.start_return(db_session, exploration_id)
        return
    if not state.is_dispatchable(clearable=True, now=datetime.utcnow()):
        await exploration_coordinator.start_return(db_session, exploration_id)
        return

    if exploration.clear_tier is not None:
        tier = exploration.clear_tier
    else:
        tier = min(state.clear_count, game_config.exploration.dispatch.escalation_cap)
    difficulty = min(5, group["base_difficulty"] + tier)
    enemy = combat_calculator.select_enemy_by_difficulty(difficulty)
    outcome = combat_calculator.calculate_combat_outcome(exploration, enemy)
    await apply_exploration_damage(db_session, exploration, outcome.health_loss)

    dweller = await dweller_crud.get(db_session, exploration.dweller_id)
    if outcome.victory and dweller is not None and not dweller.is_dead:
        table = loot_table(group["loot_table"])
        if table is not None:
            caps = random.randint(table["caps"]["min"], table["caps"]["max"])
            caps = int(caps * (1 + game_config.exploration.dispatch.reward_per_tier * tier))
            exploration.total_caps_found += caps
            for entry in table["items"]:
                item = loot_calculator.roll_item(exploration.dweller_luck, entry["type"], entry["rarity"])
                apply_loot_find(
                    exploration,
                    item_name=item.name,
                    rarity=item.rarity,
                    item_type=entry["type"],
                    caps=0,
                )
        now = datetime.utcnow()
        state.cleared_at = now
        state.reclear_available_at = now + timedelta(hours=group["reclear_hours"])
        state.clear_count += 1
        db_session.add(state)

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
                commit=False,
            )

    db_session.add(exploration)
    # Flush the loot/clear-state work before the return leg re-locks the run:
    # start_return's vault claim re-reads the exploration with populate_existing,
    # which would otherwise discard the staged haul.
    await db_session.flush()
    await exploration_coordinator.start_return(db_session, exploration_id)
