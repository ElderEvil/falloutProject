"""Arrival resolution for targeted dispatch runs (issue 772, phase 2).

A dispatch run suppresses random events and resolves exactly once on arrival:
fight the tier-scaled enemy, roll the place's loot table on a win, mark the
point cleared, then start the return leg so the haul travels home.
"""

import logging
import random
from datetime import datetime, timedelta
from operator import itemgetter

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud import world_location as crud_world_location
from app.schemas.exploration_event import EnemySchema
from app.services.exploration import data_loader
from app.services.exploration.combat_calculator import combat_calculator
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.event_service import apply_exploration_damage, apply_loot_find
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration.loot_calculator import loot_calculator
from app.utils.place_groups import get_place_group
from app.utils.place_loot import loot_table

logger = logging.getLogger(__name__)


def _select_enemy_at_difficulty(difficulty: int) -> EnemySchema:
    """Pick the enemy at the requested difficulty, or the nearest at-or-below."""
    enemies = data_loader.load_enemies()
    if not enemies:
        return EnemySchema(name="Wasteland Creature", difficulty=1, min_damage=5, max_damage=15)
    at_or_below = [enemy for enemy in enemies if enemy["difficulty"] <= difficulty]
    if not at_or_below:
        at_or_below = [min(enemies, key=itemgetter("difficulty"))]
    return EnemySchema(**max(at_or_below, key=itemgetter("difficulty")))


def _roll_item(entry: dict, luck: int):
    """Roll one loot-table entry into an item schema at its rarity floor."""
    item_type = entry["type"]
    rarity = entry["rarity"]
    if item_type == "weapon":
        return loot_calculator.select_random_weapon(luck, min_rarity=rarity)
    if item_type == "outfit":
        return loot_calculator.select_random_outfit(luck, min_rarity=rarity)
    return loot_calculator.select_random_junk(luck, min_rarity=rarity)


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

    tier = min(state.clear_count, game_config.exploration.dispatch.escalation_cap)
    difficulty = min(5, group["base_difficulty"] + tier)
    enemy = _select_enemy_at_difficulty(difficulty)
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
                item = _roll_item(entry, exploration.dweller_luck)
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

    db_session.add(exploration)
    # Flush the loot/clear-state work before the return leg re-locks the run:
    # start_return's vault claim re-reads the exploration with populate_existing,
    # which would otherwise discard the staged haul.
    await db_session.flush()
    await exploration_coordinator.start_return(db_session, exploration_id)
