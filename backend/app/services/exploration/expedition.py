"""Resolution engine for interactive expedition sites (experimental).

Runs hand-authored multi-room sites (see ``data/exploration/expedition_sites.json``):
combat reuses ``combat_calculator``, loot reuses ``loot_calculator`` plus the shared
``apply_loot_find``/``apply_exploration_damage`` appliers, so site numbers stay
consistent with timed events. Every resolution appends a ``site`` record to the
exploration event log; run state lives in ``expedition_run`` rows.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import SPECIAL_STATS
from app.crud import dweller as dweller_crud
from app.models.dweller import Dweller
from app.models.exploration import ExpeditionRun, ExpeditionRunStatus, Exploration
from app.schemas.expedition import (
    AvailableSiteView,
    EnemySpec,
    ExpeditionResolveRequest,
    NodeBranch,
    NodeOptionView,
    NodeOutcome,
    SiteDefinition,
    SiteNodeView,
    SiteRoomView,
    rarity_meets_floor,
)
from app.schemas.exploration_event import CombatOutcomeSchema, EnemySchema, LootItemSchema
from app.services.exploration import data_loader
from app.services.exploration.combat_calculator import combat_calculator
from app.services.exploration.event_service import (
    apply_exploration_damage,
    apply_exploration_radiation,
    apply_loot_find,
)
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration.loot_calculator import loot_calculator
from app.services.notification_service import notification_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

ANTI_FARM_DAYS = 7
CACHE_CAPS = {"small": (5, 15), "standard": (10, 30), "rich": (20, 50)}
STAT_SNAPSHOT_FIELDS = {stat: f"dweller_{stat}" for stat in SPECIAL_STATS}


@dataclass
class BranchResult:
    """Accumulated effects of one applied branch."""

    texts: list[str] = field(default_factory=list)
    damage_taken: int = 0
    caps_gained: int = 0
    loot_gained: list[str] = field(default_factory=list)
    dweller_died: bool = False
    defeated: bool = False
    # Serialized EnemySpec dicts of the full pack fought; persisted into run.flags for retry + XP credit.
    fought_enemies: list[dict] = field(default_factory=list)
    # Per-enemy outcomes in fight order; surfaced to the client as the battle feed.
    combat: list[dict] = field(default_factory=list)


def success_odds(stat_value: int, difficulty: int) -> float:
    """Display odds for d20 + stat*2 >= 10 + difficulty*2, clamped to 5%-95%."""
    need = _check_threshold(stat_value, difficulty)
    return min(0.95, max(0.05, (21 - need) / 20))


def roll_check(stat_value: int, difficulty: int) -> bool:
    """Roll d20 + stat*2 against 10 + difficulty*2."""
    return random.randint(1, 20) >= _check_threshold(stat_value, difficulty)


def _check_threshold(stat_value: int, difficulty: int) -> int:
    return 10 + 2 * (difficulty - stat_value)


def resolve_enemy_spec(spec: EnemySpec) -> EnemySchema:
    """Build an enemy from an inline boss spec or the shared enemy table."""
    if spec.min_damage is not None and spec.max_damage is not None:
        return EnemySchema(
            name=spec.name,
            difficulty=spec.difficulty or 1,
            min_damage=spec.min_damage,
            max_damage=spec.max_damage,
        )
    table = {enemy["name"].lower(): enemy for enemy in data_loader.load_enemies()}
    entry = table.get(spec.name.lower())
    if entry is None:
        raise ValidationException(f"Unknown expedition enemy: {spec.name!r}")
    return EnemySchema(**entry)


def _require_floor_eligible(site: SiteDefinition, item_type: str, floor: str) -> None:
    """Reject site content whose reward floor has no catalog item at or above it (authoring error)."""
    if not loot_calculator.has_eligible(item_type, floor):
        raise ValidationException(f"Site {site.id}: no {item_type} at or above rarity {floor!r} in the catalog")


def validate_site_content(site: SiteDefinition) -> None:
    """Fail fast on authoring errors (bad stats, bad enemies, unsatisfiable floors) at entry time."""
    for room in site.rooms:
        node = room.node
        for stat in [option.stat for option in node.options] + ([node.stat] if node.stat else []):
            if stat not in STAT_SNAPSHOT_FIELDS:
                raise ValidationException(f"Unknown stat {stat!r} in site {site.id}")
        for spec in node.enemies:
            resolve_enemy_spec(spec)
        for branch in (branch for option in node.options for branch in (option.success, option.failure)):
            for spec in branch.combat_enemies or []:
                resolve_enemy_spec(spec)
            if branch.cache_item is not None and branch.cache_floor is not None:
                _require_floor_eligible(site, branch.cache_item, branch.cache_floor)
    vault = site.reward_vault
    if vault.item is not None and vault.item.floor is not None:
        _require_floor_eligible(site, vault.item.type, vault.item.floor)


def _stat_value(exploration: Exploration, stat: str) -> int:
    return int(getattr(exploration, STAT_SNAPSHOT_FIELDS[stat]))


async def _get_exploration(db_session: AsyncSession, exploration_id: UUID4) -> Exploration:
    exploration = await crud.exploration.get(db_session, exploration_id)
    if exploration is None:
        raise ResourceNotFoundException(Exploration, identifier=exploration_id)
    return exploration


async def _get_open_run(db_session: AsyncSession, exploration_id: UUID4) -> ExpeditionRun:
    run = await crud.expedition_run.get_open_for_exploration_for_update(db_session, exploration_id)
    if run is None:
        raise ValidationException("No open expedition run for this exploration")
    return run


async def _site_block_reason(
    db_session: AsyncSession, vault_id: UUID4, site_id: str, *, include_open: bool = True
) -> Literal["open", "cooldown"] | None:
    """Return the vault/site gate that prevents a new entry or finale payout."""
    if (
        include_open
        and await crud.expedition_run.get_open_for_vault_site(db_session, vault_id=vault_id, site_id=site_id)
        is not None
    ):
        return "open"
    recent = await crud.expedition_run.get_recent_terminal(
        db_session,
        vault_id=vault_id,
        site_id=site_id,
        since=datetime.utcnow() - timedelta(days=ANTI_FARM_DAYS),
    )
    return "cooldown" if recent is not None else None


async def _log_site_event(db_session: AsyncSession, exploration: Exploration, description: str) -> None:
    exploration.add_event(event_type="site", description=description)
    db_session.add(exploration)
    await db_session.flush()


def _roll_item(luck: int, item_type: str, min_rarity: str | None = None) -> LootItemSchema:
    """One luck-weighted item roll, or a floor-guaranteed pick when min_rarity is set."""
    if item_type == "weapon":
        return loot_calculator.select_random_weapon(luck, min_rarity=min_rarity)
    if item_type == "outfit":
        return loot_calculator.select_random_outfit(luck, min_rarity=min_rarity)
    return loot_calculator.select_random_junk(luck, min_rarity=min_rarity)


def roll_gear(luck: int, item_type: str, floor: str | None, attempts: int = 3) -> LootItemSchema:
    """Roll an item with a guaranteed rarity floor (bounded rerolls, eligible-pool fallback)."""
    if floor is None:
        return _roll_item(luck, item_type)
    for _ in range(max(1, attempts)):
        candidate = _roll_item(luck, item_type)
        if rarity_meets_floor(candidate.rarity, floor):
            return candidate
    return _roll_item(luck, item_type, min_rarity=floor)


async def _apply_branch(
    db_session: AsyncSession,
    exploration: Exploration,
    luck: int,
    branch: NodeBranch,
    result: BranchResult,
) -> None:
    """Apply one terminal branch: cache, combat, trap, trade, or nothing."""
    if branch.cache_tier is not None:
        caps_min, caps_max = CACHE_CAPS[branch.cache_tier]
        caps = random.randint(caps_min, caps_max)
        exploration.total_caps_found += caps
        result.caps_gained += caps
        result.texts.append(f"Cache searched: +{caps} caps.")
        item_type = branch.cache_item or ("junk" if branch.cache_tier != "small" else None)
        if item_type is not None:
            item = roll_gear(luck, item_type, branch.cache_floor)
            apply_loot_find(exploration, item_name=item.name, rarity=item.rarity, item_type=item_type, caps=0)
            result.loot_gained.append(f"{item.name} ({item.rarity})")
            result.texts.append(f"Found {item.name} ({item.rarity}).")
    if branch.combat_enemies:
        await _fight_pack(db_session, exploration, branch.combat_enemies, result)
        if result.defeated or result.dweller_died:
            return
    if branch.trap_damage_min is not None:
        damage = random.randint(branch.trap_damage_min, branch.trap_damage_max or branch.trap_damage_min)
        await _take_damage(db_session, exploration, damage, result)
    if branch.trade_cost_caps:
        exploration.total_caps_found = max(0, exploration.total_caps_found - branch.trade_cost_caps)
        result.texts.append(f"Traded {branch.trade_cost_caps} caps.")


async def _take_damage(db_session: AsyncSession, exploration: Exploration, damage: int, result: BranchResult) -> None:
    await apply_exploration_damage(db_session, exploration, damage)
    result.damage_taken += damage
    dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
    if dweller_obj.is_dead:
        result.dweller_died = True
        result.texts.append(f"Took {damage} damage. The dweller died in the wasteland.")
    else:
        result.texts.append(f"Took {damage} damage.")


async def _fight_enemy(
    db_session: AsyncSession, exploration: Exploration, enemy: EnemySchema, result: BranchResult
) -> CombatOutcomeSchema:
    outcome = combat_calculator.calculate_combat_outcome(exploration, enemy)
    if outcome.victory:
        result.texts.append(f"Defeated {enemy.name}!")
    else:
        result.texts.append(f"Overpowered by {enemy.name}!")
    result.combat.append({"enemy": enemy.name, "victory": outcome.victory, "damage_taken": outcome.health_loss})
    await _take_damage(db_session, exploration, outcome.health_loss, result)
    return outcome


async def _fight_pack(
    db_session: AsyncSession, exploration: Exploration, enemies: list[EnemySpec], result: BranchResult
) -> None:
    """Fight a pack in order, stopping at defeat or death and retaining it for retries."""
    result.fought_enemies = [spec.model_dump() for spec in enemies]
    for spec in enemies:
        outcome = await _fight_enemy(db_session, exploration, resolve_enemy_spec(spec), result)
        if not outcome.victory:
            result.defeated = True
            return
        if result.dweller_died:
            return


def _find_option(node_options: list, choice_id: str | None, *, required: bool):
    if choice_id is None:
        if required:
            raise ValidationException("This room needs a choice: pass choice_id")
        return None
    for option in node_options:
        if option.id == choice_id:
            return option
    raise ValidationException(f"Unknown choice {choice_id!r} for this room")


async def _resolve_choice_branch(
    db_session: AsyncSession,
    exploration: Exploration,
    option,
    result: BranchResult,
) -> None:
    stat_value = _stat_value(exploration, option.stat)
    if roll_check(stat_value, option.difficulty):
        result.texts.append(f"{option.label}: success!")
        await _apply_branch(db_session, exploration, _stat_value(exploration, "luck"), option.success, result)
    else:
        result.texts.append(f"{option.label}: failed.")
        if option.failure.trade_cost_caps and exploration.total_caps_found < option.failure.trade_cost_caps:
            result.texts.append("No caps to salvage it with.")
            return
        await _apply_branch(db_session, exploration, _stat_value(exploration, "luck"), option.failure, result)


async def _resolve_node(
    db_session: AsyncSession,
    exploration: Exploration,
    site: SiteDefinition,
    room_index: int,
    choice_id: str | None,
    result: BranchResult,
) -> bool:
    """Resolve one room node. Returns True when the finale vault was paid."""
    room = site.rooms[room_index]
    node = room.node
    luck = _stat_value(exploration, "luck")

    if node.kind == "combat":
        await _fight_pack(db_session, exploration, node.enemies, result)
        if result.defeated or result.dweller_died:
            return False
    elif node.kind == "choice":
        option = _find_option(node.options, choice_id, required=True)
        if option.success.trade_cost_caps and exploration.total_caps_found < option.success.trade_cost_caps:
            result.texts.append(f"{option.label}: success, but short on caps — the deal falls back.")
            await _apply_branch(db_session, exploration, luck, option.failure, result)
        else:
            await _resolve_choice_branch(db_session, exploration, option, result)
    elif node.kind == "trap":
        if node.options:
            option = _find_option(node.options, choice_id, required=True)
            await _resolve_choice_branch(db_session, exploration, option, result)
        else:
            damage = random.randint(node.damage_min or 0, node.damage_max or 0)
            await _take_damage(db_session, exploration, damage, result)
        if node.radiation:
            await apply_exploration_radiation(db_session, exploration, node.radiation)
    elif node.kind == "finale":
        full_vault = True
        if node.stat is not None and node.difficulty is not None:
            full_vault = roll_check(_stat_value(exploration, node.stat), node.difficulty)
            result.texts.append("Terminal cracked: full vault!" if full_vault else "Terminal resisted: half vault.")
        await _pay_reward_vault(exploration, site, full=full_vault, result=result)
        return True
    else:
        raise ValidationException(f"Unknown node kind {node.kind!r} in site {site.id}")
    return False


async def _pay_reward_vault(
    exploration: Exploration,
    site: SiteDefinition,
    *,
    full: bool,
    result: BranchResult,
) -> None:
    vault = site.reward_vault
    caps_min, caps_max = (vault.caps_min, vault.caps_max) if full else (vault.caps_min // 2, vault.caps_max // 2)
    caps = random.randint(caps_min, caps_max)
    exploration.total_caps_found += caps
    result.caps_gained += caps
    result.texts.append(f"Reward vault: +{caps} caps.")
    if vault.item is not None:
        attempts = vault.item.attempts if full else 1
        item = roll_gear(_stat_value(exploration, "luck"), vault.item.type, vault.item.floor, attempts)
        apply_loot_find(exploration, item_name=item.name, rarity=item.rarity, item_type=vault.item.type, caps=0)
        result.loot_gained.append(f"{item.name} ({item.rarity})")
        result.texts.append(f"Claimed {item.name} ({item.rarity}).")
    for _ in range(vault.junk_bundles):
        junk = loot_calculator.select_random_junk(_stat_value(exploration, "luck"))
        apply_loot_find(exploration, item_name=junk.name, rarity=junk.rarity, item_type="junk", caps=0)
        result.loot_gained.append(f"{junk.name} ({junk.rarity})")
    for _ in range(vault.stimpaks):
        apply_loot_find(exploration, item_name="Stimpak", rarity="Common", item_type="stimpak", caps=0)
        result.loot_gained.append("Stimpak")


def build_view(
    exploration_id,
    site: SiteDefinition,
    run: ExpeditionRun,
    exploration: Exploration,
    outcome: NodeOutcome | None = None,
    finale_paid: bool = False,
    defeated: bool | None = None,
    dweller: Dweller | None = None,
) -> SiteRoomView:
    """Project the run row plus site JSON into the player-facing room view."""
    room_index = min(run.room_cursor, len(site.rooms) - 1)
    room = site.rooms[room_index]
    if defeated is None:
        pending = run.flags.get("pending_fight")
        defeated = bool(run.is_open() and pending is not None and pending.get("room_id") == room.id)
    options = [
        NodeOptionView(
            id=option.id,
            label=option.label,
            stat=option.stat,
            difficulty=option.difficulty,
            success_odds=success_odds(_stat_value(exploration, option.stat), option.difficulty),
        )
        for option in room.node.options
    ]
    enemies = [spec.name for spec in room.node.enemies]
    for option in room.node.options:
        enemies.extend(spec.name for spec in (option.failure.combat_enemies or []))
    return SiteRoomView(
        exploration_id=exploration_id,
        site_id=site.id,
        site_name=site.name,
        room_index=room_index,
        room_total=len(site.rooms),
        room_name=room.name,
        flavor=room.flavor,
        node=SiteNodeView(kind=room.node.kind, prompt=room.node.prompt, options=options, enemy_names=enemies),
        can_retreat=run.is_open(),
        status=run.status.value,
        outcome=outcome,
        finale_paid=finale_paid,
        defeated=defeated,
        dweller_health=dweller.health if dweller is not None else 0,
        dweller_max_health=dweller.effective_max_health if dweller is not None else 0,
    )


async def _refresh_run(db_session: AsyncSession, run: ExpeditionRun) -> ExpeditionRun:
    db_session.add(run)
    await db_session.flush()
    await db_session.refresh(run)
    return run


class ExpeditionService:
    """Enter, resolve, retreat, and inspect expedition site runs."""

    async def enter_run(self, db_session: AsyncSession, exploration_id: UUID4, site_id: str) -> SiteRoomView:
        """Start a site run on an active exploration (anti-farm + level gates enforced)."""
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
        if not exploration.is_active():
            raise ValidationException("Expedition sites need an active exploration")
        site = data_loader.get_expedition_site(site_id)
        if site is None:
            raise ValidationException(f"Unknown expedition site: {site_id!r}")
        validate_site_content(site)
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        if dweller_obj.is_dead:
            raise ValidationException("A dead dweller cannot enter an expedition site")
        if dweller_obj.level < site.min_dweller_level:
            raise ValidationException(
                f"{site.name} needs dweller level {site.min_dweller_level} (dweller is {dweller_obj.level})"
            )
        if await crud.expedition_run.get_open_for_exploration(db_session, exploration_id) is not None:
            raise ResourceConflictException("This exploration already has an open expedition run")
        blocked = await _site_block_reason(db_session, exploration.vault_id, site_id)
        if blocked == "open":
            raise ResourceConflictException(f"{site_id} already has an open expedition run")
        if blocked == "cooldown":
            raise ResourceConflictException(f"{site.name} is quiet after a recent expedition")
        run = await crud.expedition_run.create_run(
            db_session,
            exploration_id=exploration_id,
            vault_id=exploration.vault_id,
            site_id=site_id,
        )
        await _log_site_event(db_session, exploration, f"Entered {site.name}: {site.rooms[0].flavor}")
        await db_session.commit()
        return build_view(exploration_id, site, run, exploration, dweller=dweller_obj)

    async def list_available_sites(self, db_session: AsyncSession, exploration_id: UUID4) -> list[AvailableSiteView]:
        """List expedition sites the dweller may currently enter (level + anti-farm gates)."""
        exploration = await _get_exploration(db_session, exploration_id)
        if not exploration.is_active():
            raise ValidationException("Expedition sites need an active exploration")
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        if dweller_obj.is_dead:
            return []
        available: list[AvailableSiteView] = []
        for site in data_loader.load_expedition_sites():
            if dweller_obj.level < site.min_dweller_level:
                continue
            if await _site_block_reason(db_session, exploration.vault_id, site.id) is not None:
                continue
            available.append(
                AvailableSiteView(
                    id=site.id,
                    name=site.name,
                    flavor=site.flavor,
                    min_dweller_level=site.min_dweller_level,
                    room_total=len(site.rooms),
                )
            )
        return available

    async def current_view(self, db_session: AsyncSession, exploration_id: UUID4) -> SiteRoomView | None:
        """Return the open run view for reconnects, or None when there is none."""
        exploration = await _get_exploration(db_session, exploration_id)
        run = await crud.expedition_run.get_open_for_exploration(db_session, exploration_id)
        if run is None:
            return None
        site = data_loader.get_expedition_site(run.site_id)
        if site is None:
            raise ValidationException(f"Unknown expedition site: {run.site_id!r}")
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        return build_view(exploration_id, site, run, exploration, dweller=dweller_obj)

    async def resolve_node(
        self, db_session: AsyncSession, exploration_id: UUID4, request: ExpeditionResolveRequest
    ) -> SiteRoomView:
        """Resolve the current room node and advance the cursor (or finish the run)."""
        db_session.info.pop("deferred_notification_deliveries", None)
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
        if not exploration.is_active():
            raise ValidationException("Expedition sites need an active exploration")
        run = await _get_open_run(db_session, exploration_id)
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        if dweller_obj.is_dead:
            run.status = ExpeditionRunStatus.DIED
            run.finished_at = datetime.utcnow()
            await _refresh_run(db_session, run)
            await db_session.commit()
            raise ValidationException("The exploring dweller is dead")
        site = data_loader.get_expedition_site(run.site_id)
        if site is None:
            raise ValidationException(f"Unknown expedition site: {run.site_id!r}")
        room = site.rooms[run.room_cursor]

        # The finale pays the reward vault; re-check the cooldown under the claim
        # so a run that outlived a terminal sibling cannot pay into a locked site.
        if room.node.kind == "finale" and await _site_block_reason(
            db_session, exploration.vault_id, run.site_id, include_open=False
        ):
            raise ValidationException(f"{site.name} is quiet after a recent expedition")

        result = BranchResult()
        pending = run.flags.get("pending_fight")
        if pending is not None and pending.get("room_id") == room.id:
            # Push-on after a defeat: replay the recorded pack; never re-roll the
            # original choice/check that led to the failed branch.
            await _fight_pack(
                db_session, exploration, [EnemySpec(**spec_dict) for spec_dict in pending["enemies"]], result
            )
            finale_paid = False
        else:
            finale_paid = await _resolve_node(db_session, exploration, site, run.room_cursor, request.choice_id, result)
        outcome = NodeOutcome(
            text=" ".join(result.texts),
            damage_taken=result.damage_taken,
            caps_gained=result.caps_gained,
            loot_gained=result.loot_gained,
            combat=result.combat,
        )
        await _log_site_event(db_session, exploration, f"{site.name} — {room.name}: {outcome.text}")

        if result.dweller_died:
            run.status = ExpeditionRunStatus.DIED
            run.finished_at = datetime.utcnow()
        elif finale_paid:
            run.status = ExpeditionRunStatus.CLEARED
            run.finished_at = datetime.utcnow()
        elif result.defeated:
            # Defeat stops the pack: stay in the room, offer push-on/retreat.
            run.status = ExpeditionRunStatus.IN_ROOM
            flags = dict(run.flags)
            flags["pending_fight"] = {"room_id": room.id, "enemies": result.fought_enemies}
            run.flags = flags
        else:
            run.status = ExpeditionRunStatus.IN_ROOM
            flags = dict(run.flags)
            flags.pop("pending_fight", None)
            credited = flags.get("credited_rooms", [])
            if result.fought_enemies and room.id not in credited:
                exploration.enemies_encountered += len(result.fought_enemies)
                flags["credited_rooms"] = [*credited, room.id]
            run.flags = flags
            run.room_cursor = min(run.room_cursor + 1, len(site.rooms) - 1)
        run = await _refresh_run(db_session, run)
        await db_session.commit()
        await notification_service.deliver_deferred_notifications(db_session)
        return build_view(
            exploration_id,
            site,
            run,
            exploration,
            outcome=outcome,
            finale_paid=finale_paid,
            defeated=result.defeated,
            dweller=dweller_obj,
        )

    async def retreat_run(self, db_session: AsyncSession, exploration_id: UUID4) -> SiteRoomView:
        """Abandon the run at a room boundary: room loot kept, finale forfeited."""
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
        if not exploration.is_active():
            raise ValidationException("Expedition sites need an active exploration")
        run = await _get_open_run(db_session, exploration_id)
        site = data_loader.get_expedition_site(run.site_id)
        if site is None:
            raise ValidationException(f"Unknown expedition site: {run.site_id!r}")
        run.status = ExpeditionRunStatus.RETREATED
        run.finished_at = datetime.utcnow()
        run = await _refresh_run(db_session, run)
        await _log_site_event(db_session, exploration, f"Retreated from {site.name} with whatever was carried.")
        await db_session.commit()
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        return build_view(exploration_id, site, run, exploration, dweller=dweller_obj)


expedition_service = ExpeditionService()
