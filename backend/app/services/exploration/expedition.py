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
from app.crud.world_snapshot import world_snapshot as world_snapshot_crud
from app.models.dweller import Dweller
from app.models.exploration import CONSUMING_STATUSES, ExpeditionRun, ExpeditionRunStatus, Exploration
from app.models.notification import NotificationType
from app.schemas.expedition import (
    AvailableSiteView,
    EnemySpec,
    ExpeditionResolveRequest,
    NodeBranch,
    NodeOptionView,
    NodeOutcome,
    SiteDefinition,
    SiteNodeView,
    SiteRoom,
    SiteRoomView,
    TriviaQuestion,
    TriviaRaider,
    rarity_meets_floor,
)
from app.schemas.exploration_event import CombatOutcomeSchema, EnemySchema, LootItemSchema
from app.services import catalog_service as data_loader
from app.services.exploration.combat_calculator import combat_calculator
from app.services.exploration.event_service import (
    apply_exploration_damage,
    apply_exploration_radiation,
    apply_loot_find,
    auto_use_supplies,
)
from app.services.exploration.locking import lock_exploration_with_vault_claim
from app.services.exploration.loot_calculator import loot_calculator
from app.services.exploration.site_combat_service import combat_view, encounter_threat, initial_combat, resolve_turn
from app.services.notification_service import notification_service
from app.services.world_generation_service import WORLD_ID
from app.utils import world_terrain
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

ANTI_FARM_DAYS = 7
ALL_SITES_SCENARIO_EVENT = "scenario_all_sites"
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

    def to_outcome(self) -> NodeOutcome:
        return NodeOutcome(
            text=" ".join(self.texts),
            damage_taken=self.damage_taken,
            caps_gained=self.caps_gained,
            loot_gained=self.loot_gained,
            combat=self.combat,
        )


@dataclass(frozen=True)
class SiteBlockState:
    """Per-vault+site expedition gate: block reason plus remaining anti-farm seconds."""

    reason: Literal["open", "cooldown"] | None = None
    cooldown_remaining_seconds: int = 0
    cleared: bool = False


@dataclass(frozen=True)
class JourneyOfferContext:
    """Trail-relative inputs that decide which sites a spatial journey offers."""

    trail: list[tuple[float, float]]
    radius: float
    consumed_site_ids: frozenset[str]


async def journey_offer_context(db_session: AsyncSession, exploration: Exploration) -> JourneyOfferContext | None:
    """Trail offer inputs for a spatial run, or None when terrain/version is unavailable."""
    if exploration.heading_degrees is None or exploration.world_version is None:
        return None
    snapshot = await world_snapshot_crud.get_version(
        db_session, world_id=WORLD_ID, generator_version=exploration.world_version
    )
    if snapshot is None:
        return None
    consumed = await crud.expedition_run.get_consumed_site_ids_for_exploration(
        db_session, exploration_id=exploration.id
    )
    return JourneyOfferContext(
        trail=[(float(step["x"]), float(step["y"])) for step in (exploration.trail or [])],
        radius=world_terrain.reveal_radius_registry(snapshot, world_terrain.SITE_REVEAL_TILES),
        consumed_site_ids=frozenset(consumed),
    )


def site_is_offered(site: SiteDefinition, context: JourneyOfferContext) -> bool:
    """True when a spatial journey offers *site*: near its trail and not yet consumed."""
    return site.id not in context.consumed_site_ids and world_terrain.path_passes_near(
        context.trail, (site.coord_x, site.coord_y), context.radius
    )


def success_odds(stat_value: int, difficulty: int) -> float:
    """Display odds for d20 + stat*2 >= 10 + difficulty*2, clamped to 5%-95%."""
    need = _check_threshold(stat_value, difficulty)
    return min(0.95, max(0.05, (21 - need) / 20))


def roll_check(stat_value: int, difficulty: int) -> bool:
    """Roll d20 + stat*2 against 10 + difficulty*2."""
    return random.randint(1, 20) >= _check_threshold(stat_value, difficulty)


def _check_threshold(stat_value: int, difficulty: int) -> int:
    return 10 + 2 * (difficulty - stat_value)


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


async def site_block_state(
    db_session: AsyncSession, vault_id: UUID4, site_id: str, *, include_open: bool = True
) -> SiteBlockState:
    """Return the vault/site expedition gate with the remaining anti-farm window."""
    if (
        include_open
        and await crud.expedition_run.get_open_for_vault_site(db_session, vault_id=vault_id, site_id=site_id)
        is not None
    ):
        return SiteBlockState(reason="open")
    recent = await crud.expedition_run.get_recent_terminal(
        db_session,
        vault_id=vault_id,
        site_id=site_id,
        since=datetime.utcnow() - timedelta(days=ANTI_FARM_DAYS),
    )
    if recent is None:
        return SiteBlockState()
    cleared = recent.status == ExpeditionRunStatus.CLEARED
    if recent.finished_at is None:
        return SiteBlockState(reason="cooldown", cleared=cleared)
    window_end = recent.finished_at + timedelta(days=ANTI_FARM_DAYS)
    remaining = max(0, int((window_end - datetime.utcnow()).total_seconds()))
    return SiteBlockState(reason="cooldown", cooldown_remaining_seconds=remaining, cleared=cleared)


async def _site_block_reason(
    db_session: AsyncSession, vault_id: UUID4, site_id: str, *, include_open: bool = True
) -> Literal["open", "cooldown"] | None:
    """Return the vault/site gate that prevents a new entry or finale payout."""
    return (await site_block_state(db_session, vault_id, site_id, include_open=include_open)).reason


async def _log_site_event(
    db_session: AsyncSession, exploration: Exploration, description: str, *, health_loss: int = 0
) -> None:
    exploration.add_event(event_type="site", description=description, health_loss=health_loss or None)
    db_session.add(exploration)
    await db_session.flush()


def roll_gear(luck: int, item_type: str, floor: str | None, attempts: int = 3) -> LootItemSchema:
    """Roll an item with a guaranteed rarity floor (bounded rerolls, eligible-pool fallback)."""
    if floor is None:
        return loot_calculator.roll_item(luck, item_type)
    for _ in range(max(1, attempts)):
        candidate = loot_calculator.roll_item(luck, item_type)
        if rarity_meets_floor(candidate.rarity, floor):
            return candidate
    return loot_calculator.roll_item(luck, item_type, min_rarity=floor)


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
        outcome = await _fight_enemy(db_session, exploration, data_loader.resolve_enemy_spec(spec), result)
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
    room: SiteRoom,
    choice_id: str | None,
    result: BranchResult,
) -> bool:
    """Resolve one room node. Returns True when the finale vault was paid."""
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


def uses_single_scene(site: SiteDefinition, *, spatial: bool) -> bool:
    """Use encounter content for spatial visits and sites without legacy rooms."""
    return site.encounter is not None and (spatial or not site.rooms)


def _rooms_for_run(site: SiteDefinition, run: ExpeditionRun) -> list[SiteRoom]:
    """Saved runs keep their original cursor; new spatial visits use one encounter."""
    if run.flags.get("single_scene"):
        if site.encounter is None:
            raise ValidationException(f"Missing encounter content for {site.id}")
        return [site.encounter]
    return site.rooms


def _pick_trivia_questions(rooms: list[SiteRoom]) -> dict[str, str]:
    """Pin one question id per trivia room at entry so a reconnect cannot reroll it."""
    return {room.id: random.choice(room.node.trivia_questions).id for room in rooms if room.node.kind == "trivia"}


def _pick_trivia_raiders(rooms: list[SiteRoom]) -> dict[str, str]:
    """Pin one raider persona per trivia room at entry, alongside its question."""
    return {room.id: random.choice(room.node.raiders).id for room in rooms if room.node.kind == "trivia"}


def _trivia_question(room: SiteRoom, run: ExpeditionRun) -> TriviaQuestion | None:
    """The question persisted for this room at entry, if any."""
    question_id = run.flags.get("trivia_questions", {}).get(room.id)
    return next((question for question in room.node.trivia_questions if question.id == question_id), None)


def _trivia_raider(room: SiteRoom, run: ExpeditionRun) -> TriviaRaider | None:
    """The raider persona persisted for this room at entry, if any."""
    raider_id = run.flags.get("trivia_raiders", {}).get(room.id)
    return next((raider for raider in room.node.raiders if raider.id == raider_id), None)


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
    rooms = _rooms_for_run(site, run)
    room_index = min(run.room_cursor, len(rooms) - 1)
    room = rooms[room_index]
    if defeated is None:
        pending = run.flags.get("pending_fight")
        defeated = run.status == ExpeditionRunStatus.DEFEATED or bool(
            run.is_open() and pending is not None and pending.get("room_id") == room.id
        )
    question_text: str | None = None
    prompt = room.node.prompt
    raider = _trivia_raider(room, run) if room.node.kind == "trivia" else None
    raider_image_url = raider.image_url if raider is not None else None
    raider_alt_image_url = raider.alt_image_url if raider is not None else None
    if room.node.kind == "trivia":
        if raider is not None:
            prompt = f"{raider.intro} {prompt}"
        question = _trivia_question(room, run)
        if question is not None and run.is_open() and not run.flags.get("combat"):
            question_text = question.prompt
            options = [NodeOptionView(id=option.id, label=option.label) for option in question.options]
        else:
            options = []
    else:
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
    enemies = (
        [enemy["name"] for enemy in run.flags["combat"]["opponents"]]
        if run.flags.get("combat")
        else [spec.name for spec in room.node.enemies]
    )
    if raider is not None and not run.flags.get("combat") and enemies:
        enemies = [raider.name, *enemies[1:]]
    for option in room.node.options:
        enemies.extend(spec.name for spec in (option.failure.combat_enemies or []))
    return SiteRoomView(
        exploration_id=exploration_id,
        site_id=site.id,
        site_name=site.name,
        room_index=room_index,
        room_total=len(rooms),
        room_name=room.name,
        room_names=[room.name for room in rooms],
        flavor=room.flavor,
        node=SiteNodeView(
            kind=room.node.kind,
            prompt=prompt,
            question=question_text,
            raider_image_url=raider_image_url,
            raider_alt_image_url=raider_alt_image_url,
            options=options,
            enemy_names=enemies,
        ),
        can_retreat=run.is_open(),
        status=run.status.value,
        outcome=outcome,
        finale_paid=finale_paid,
        defeated=defeated,
        dweller_health=dweller.health if dweller is not None else 0,
        dweller_max_health=dweller.effective_max_health if dweller is not None else 0,
        scene_id=site.scene_id,
        lore=site.lore if run.flags.get("single_scene") else "",
        combat_state=combat_view(run.flags["combat"], dweller) if dweller and run.flags.get("combat") else None,
    )


async def _refresh_run(db_session: AsyncSession, run: ExpeditionRun) -> ExpeditionRun:
    db_session.add(run)
    await db_session.flush()
    await db_session.refresh(run)
    return run


async def _reopen_run(db_session: AsyncSession, run: ExpeditionRun) -> ExpeditionRun:
    """Resume a retreated run at its saved cursor, clearing the terminal stamp."""
    run.status = ExpeditionRunStatus.IN_ROOM
    run.finished_at = None
    return await _refresh_run(db_session, run)


def _arrived_home(exploration: Exploration) -> bool:
    return (
        exploration.is_returning()
        and exploration.paused_at is None
        and exploration.return_completes_at is not None
        and exploration.return_completes_at <= datetime.utcnow()
    )


def _is_all_sites_scenario(exploration: Exploration) -> bool:
    return any(event.get("event") == ALL_SITES_SCENARIO_EVENT for event in exploration.events or [])


def _scenario_single_scene_only(exploration: Exploration) -> bool:
    for event in exploration.events or []:
        if event.get("event") == ALL_SITES_SCENARIO_EVENT:
            return bool(event.get("single_scene_only", False))
    return False


def _scenario_site_id(exploration: Exploration) -> str | None:
    for event in exploration.events or []:
        if event.get("event") == ALL_SITES_SCENARIO_EVENT:
            site_id = event.get("scenario_site_id")
            return str(site_id) if site_id else None
    return None


def _scenario_choice_only(exploration: Exploration) -> bool:
    for event in exploration.events or []:
        if event.get("event") == ALL_SITES_SCENARIO_EVENT:
            return bool(event.get("choice_only", False))
    return False


class ExpeditionService:
    """Enter, resolve, retreat, and inspect expedition site runs."""

    async def discover_sites(self, db_session: AsyncSession, exploration_id: UUID4) -> None:
        """Persist trail discoveries and their inbox reports atomically, once per journey/site.

        Movement commits before this operation. This method owns the discovery
        transaction; vault -> exploration locks serialize ticks with site entry
        and return finalization. Transport delivery follows the commit.
        """
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
        if (
            not exploration.is_in_progress()
            or exploration.team_id is not None
            or exploration.heading_degrees is None
            or exploration.paused_at is not None
            or _arrived_home(exploration)
        ):
            return
        # Missing world data must not turn the legacy catalog fallback into discoveries.
        context = await journey_offer_context(db_session, exploration)
        if context is None:
            return
        found = {event.get("site_id") for event in exploration.events if event.get("event") == "site_found"}
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        if dweller_obj.is_dead:
            return
        sites = [
            site
            for site in await self._available_sites(db_session, exploration, dweller_obj, context)
            if site.id not in found
        ]
        if not sites:
            return
        vault = await crud.vault.get(db_session, exploration.vault_id)
        try:
            for site in sites:
                metadata = {
                    "event": "site_found",
                    "exploration_id": str(exploration.id),
                    "site_id": site.id,
                    "site_name": site.name,
                }
                message = f"{dweller_obj.first_name} found {site.name}. Enter before the dweller arrives home."
                record = exploration.add_event(event_type="site", description=message)
                record.update(metadata)
                await notification_service.create_and_send(
                    db_session,
                    vault.user_id,
                    NotificationType.EXPLORATION_UPDATE,
                    "Expedition site found",
                    message,
                    vault_id=exploration.vault_id,
                    from_dweller_id=exploration.dweller_id,
                    meta_data=metadata,
                    commit=False,
                )
            await db_session.commit()
            await notification_service.deliver_deferred_notifications(db_session)
        finally:
            notification_service.discard_deferred_notifications(db_session)

    async def _require_site_near_trail(self, db_session: AsyncSession, exploration: Exploration, site) -> None:
        """Reject a spatial entry whose site was never traveled past (list/enter parity)."""
        context = await journey_offer_context(db_session, exploration)
        if context is None:
            return
        if not world_terrain.path_passes_near(context.trail, (site.coord_x, site.coord_y), context.radius):
            raise ValidationException(f"{site.name} is not on this journey's traveled path")

    async def enter_run(self, db_session: AsyncSession, exploration_id: UUID4, site_id: str) -> SiteRoomView:
        """Start (or resume) a site run on an in-progress exploration.

        Re-entering the same open site is an idempotent reconnect; re-entering a
        retreated site resumes from its saved room cursor. A different site still
        conflicts with the one open run, and a consumed site stays spent.
        """
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
        if not exploration.is_in_progress():
            raise ValidationException("Expedition sites need an active exploration")
        if exploration.team_id is not None:
            raise ValidationException("Party dispatches cannot enter expedition sites")
        site = data_loader.get_expedition_site(site_id)
        if site is None:
            raise ValidationException(f"Unknown expedition site: {site_id!r}")
        scenario_site_id = _scenario_site_id(exploration)
        choice_only = _scenario_choice_only(exploration)
        if scenario_site_id is not None and site_id != scenario_site_id:
            raise ValidationException(f"This scenario is limited to {scenario_site_id}")
        if choice_only and (site.encounter is None or site.encounter.node.kind != "choice"):
            raise ValidationException("This scenario only offers stat-check encounters")
        if site.scenario_only and scenario_site_id != site_id and not choice_only:
            raise ValidationException(f"{site.name} is only available through its scenario")
        if _is_all_sites_scenario(exploration) and _scenario_single_scene_only(exploration) and len(site.rooms) > 1:
            raise ValidationException(f"{site.name} uses a multi-room encounter, disabled for this scenario")
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        if dweller_obj.is_dead:
            raise ValidationException("A dead dweller cannot enter an expedition site")
        if dweller_obj.level < site.min_dweller_level:
            raise ValidationException(
                f"{site.name} needs dweller level {site.min_dweller_level} (dweller is {dweller_obj.level})"
            )
        open_run = await crud.expedition_run.get_open_for_exploration_for_update(db_session, exploration_id)
        if open_run is not None:
            if open_run.site_id == site_id:
                return build_view(exploration_id, site, open_run, exploration, dweller=dweller_obj)
            raise ResourceConflictException("This exploration already has an open expedition run")
        if _arrived_home(exploration):
            raise ValidationException("The dweller has arrived home; this journey's site offers have expired")
        if (
            await crud.expedition_run.get_consumed_for_exploration_site(
                db_session, exploration_id=exploration_id, site_id=site_id
            )
            is not None
        ):
            raise ResourceConflictException(f"{site.name} is already spent for this journey")
        if exploration.heading_degrees is not None:
            await self._require_site_near_trail(db_session, exploration, site)
        else:
            blocked = await _site_block_reason(db_session, exploration.vault_id, site_id)
            if blocked == "open":
                raise ResourceConflictException(f"{site_id} already has an open expedition run")
            if blocked == "cooldown" and not _is_all_sites_scenario(exploration):
                raise ResourceConflictException(f"{site.name} is quiet after a recent expedition")

        latest = await crud.expedition_run.get_latest_for_exploration_site(
            db_session, exploration_id=exploration_id, site_id=site_id
        )
        if latest is not None and latest.status == ExpeditionRunStatus.RETREATED:
            run = await _reopen_run(db_session, latest)
        else:
            run = await crud.expedition_run.create_run(
                db_session,
                exploration_id=exploration_id,
                vault_id=exploration.vault_id,
                site_id=site_id,
            )
            spatial = exploration.heading_degrees is not None
            single_scene = uses_single_scene(site, spatial=spatial)
            rooms = [site.encounter] if single_scene and site.encounter is not None else site.rooms
            flags = {
                **run.flags,
                "trivia_questions": _pick_trivia_questions(rooms),
                "trivia_raiders": _pick_trivia_raiders(rooms),
            }
            if single_scene:
                flags["single_scene"] = True
                if site.encounter is not None and site.encounter.node.kind == "combat":
                    flags["combat"] = initial_combat(site)
            run.flags = flags

        from app.services.exploration_service import exploration_service

        await exploration_service.pause_for_encounter(db_session, exploration)
        await _log_site_event(db_session, exploration, f"Entered {site.name}: {_rooms_for_run(site, run)[0].flavor}")
        await db_session.commit()
        return build_view(exploration_id, site, run, exploration, dweller=dweller_obj)

    async def list_available_sites(self, db_session: AsyncSession, exploration_id: UUID4) -> list[AvailableSiteView]:
        """List expedition sites the dweller may currently enter.

        Spatial runs are offered the catalog sites near their traveled trail
        (one-time journey consumption replaces the vault-wide repeat cooldown);
        legacy runs keep catalog listing with the anti-farm gates.
        """
        exploration = await _get_exploration(db_session, exploration_id)
        if not exploration.is_in_progress():
            raise ValidationException("Expedition sites need an active exploration")
        if exploration.team_id is not None or _arrived_home(exploration):
            return []
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        if dweller_obj.is_dead:
            return []
        context = await journey_offer_context(db_session, exploration)
        sites = await self._available_sites(db_session, exploration, dweller_obj, context)
        return [
            AvailableSiteView(
                id=site.id,
                name=site.name,
                flavor=site.flavor,
                min_dweller_level=site.min_dweller_level,
                room_total=1
                if (single := uses_single_scene(site, spatial=exploration.heading_degrees is not None))
                else len(site.rooms),
                scene_id=site.scene_id,
                enemy_names=[spec.name for spec in site.encounter.node.enemies] if single and site.encounter else [],
                threat=encounter_threat(site, dweller_obj)
                if single and site.encounter and site.encounter.node.kind == "combat"
                else None,
            )
            for site in sites
        ]

    async def _available_sites(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        dweller: Dweller,
        context: JourneyOfferContext | None,
    ) -> list[SiteDefinition]:
        """Share eligibility inputs between the picker and discovery without rebuilding views."""
        consumed = (
            context.consumed_site_ids
            if context is not None
            else await crud.expedition_run.get_consumed_site_ids_for_exploration(
                db_session, exploration_id=exploration.id
            )
        )
        available = []
        scenario_site_id = _scenario_site_id(exploration)
        choice_only = _scenario_choice_only(exploration)
        for site in data_loader.load_expedition_sites():
            if site.scenario_only and scenario_site_id != site.id and not choice_only:
                continue
            if scenario_site_id is not None and site.id != scenario_site_id:
                continue
            if choice_only and (site.encounter is None or site.encounter.node.kind != "choice"):
                continue
            if dweller.level < site.min_dweller_level or site.id in consumed:
                continue
            if _is_all_sites_scenario(exploration) and _scenario_single_scene_only(exploration) and len(site.rooms) > 1:
                continue
            if context is not None:
                if not site_is_offered(site, context):
                    continue
            else:
                blocked = await _site_block_reason(db_session, exploration.vault_id, site.id)
                if blocked is not None and not (_is_all_sites_scenario(exploration) and blocked == "cooldown"):
                    continue
            available.append(site)
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
        if not exploration.is_in_progress():
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
        rooms = _rooms_for_run(site, run)
        room = rooms[run.room_cursor]
        if run.flags.get("single_scene") and room.node.kind == "combat":
            try:
                return await self._resolve_scene_combat_transaction(
                    db_session, exploration, run, site, dweller_obj, request
                )
            finally:
                notification_service.discard_deferred_notifications(db_session)
        if room.node.kind == "trivia":
            try:
                if run.flags.get("combat"):
                    return await self._resolve_scene_combat_transaction(
                        db_session, exploration, run, site, dweller_obj, request
                    )
                return await self._resolve_trivia_transaction(
                    db_session, exploration, run, site, room, request, dweller_obj
                )
            finally:
                notification_service.discard_deferred_notifications(db_session)

        # The finale pays the reward vault; re-check eligibility under the claim
        # so a run that outlived a terminal sibling cannot pay into a locked site.
        # Spatial runs check journey consumption instead of the vault cooldown.
        if room.node.kind == "finale":
            if exploration.heading_degrees is not None:
                consumed = await crud.expedition_run.get_consumed_for_exploration_site(
                    db_session, exploration_id=exploration_id, site_id=run.site_id
                )
                if consumed is not None:
                    raise ValidationException(f"{site.name} is already spent for this journey")
            elif not _is_all_sites_scenario(exploration) and await _site_block_reason(
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
            finale_paid = await _resolve_node(db_session, exploration, site, room, request.choice_id, result)
        outcome = result.to_outcome()
        await _log_site_event(
            db_session,
            exploration,
            f"{site.name} — {room.name}: {outcome.text}",
            health_loss=result.damage_taken,
        )
        await auto_use_supplies(db_session, exploration)

        if not (result.dweller_died or result.defeated):
            flags = dict(run.flags)
            flags.pop("pending_fight", None)
            credited = flags.get("credited_rooms", [])
            if result.fought_enemies and room.id not in credited:
                exploration.enemies_encountered += len(result.fought_enemies)
                flags["credited_rooms"] = [*credited, room.id]
            run.flags = flags
        scene_cleared = (
            bool(run.flags.get("single_scene")) and not finale_paid and not result.defeated and not result.dweller_died
        )
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
        elif scene_cleared:
            run.status = ExpeditionRunStatus.CLEARED
            run.finished_at = datetime.utcnow()
        else:
            run.status = ExpeditionRunStatus.IN_ROOM
            run.room_cursor = min(run.room_cursor + 1, len(rooms) - 1)
        run = await _refresh_run(db_session, run)
        if run.status in CONSUMING_STATUSES:
            from app.services.exploration_service import exploration_service

            exploration_service.resume_from_encounter(exploration)
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

    async def _resolve_trivia_transaction(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        run: ExpeditionRun,
        site: SiteDefinition,
        room: SiteRoom,
        request: ExpeditionResolveRequest,
        dweller: Dweller,
    ) -> SiteRoomView:
        """Judge one trivia answer: a correct answer pays once, a wrong one starts the fight.

        The question was pinned in ``run.flags`` at entry, so a repeat or reconnect
        judges the same question and the same answer key. A cleared run has no open
        row, so a duplicate submission cannot pay the vault twice.
        """
        question = _trivia_question(room, run)
        if question is None:
            raise ValidationException("This trivia encounter has no persisted question")
        if request.choice_id is None:
            raise ValidationException("This room needs an answer: pass choice_id")
        if request.choice_id not in {option.id for option in question.options}:
            raise ValidationException(f"Unknown answer {request.choice_id!r} for this question")

        result = BranchResult()
        raider = _trivia_raider(room, run)
        correct = request.choice_id == question.correct_option_id
        if correct:
            await _pay_reward_vault(exploration, site, full=True, result=result)
            result.texts.insert(
                0,
                f"Correct answer — {raider.name} {raider.correct_line}."
                if raider is not None
                else "Correct answer — the raider hands over the toll stash.",
            )
            run.status = ExpeditionRunStatus.CLEARED
            run.finished_at = datetime.utcnow()
            from app.services.exploration_service import exploration_service

            exploration_service.resume_from_encounter(exploration)
        else:
            result.texts.append(
                f"Wrong answer — {raider.name} {raider.wrong_line}."
                if raider is not None
                else "Wrong answer — the raider attacks!"
            )
            combat = initial_combat(site)
            if raider is not None and combat["opponents"]:
                combat["opponents"][0]["name"] = raider.name
                combat["opponents"][0]["image_url"] = raider.alt_image_url or raider.image_url
            run.flags = {**run.flags, "combat": combat}

        outcome = result.to_outcome()
        await _log_site_event(db_session, exploration, f"{site.name}: {outcome.text}")
        await auto_use_supplies(db_session, exploration)
        run = await _refresh_run(db_session, run)
        if correct:
            vault = await crud.vault.get(db_session, exploration.vault_id)
            raider_name = raider.name if raider is not None else "the raider"
            await notification_service.create_and_send(
                db_session,
                vault.user_id,
                NotificationType.EXPLORATION_UPDATE,
                "Expedition site cleared",
                f"{dweller.first_name} answered {raider_name} and secured {site.name}. Rewards added to the expedition haul.",
                vault_id=exploration.vault_id,
                from_dweller_id=dweller.id,
                meta_data={"event": "site_cleared", "exploration_id": str(exploration.id), "site_id": site.id},
                commit=False,
            )
        await db_session.commit()
        await notification_service.deliver_deferred_notifications(db_session)
        return build_view(
            exploration.id,
            site,
            run,
            exploration,
            outcome=outcome,
            finale_paid=correct,
            defeated=False,
            dweller=dweller,
        )

    async def _resolve_scene_combat_transaction(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        run: ExpeditionRun,
        site: SiteDefinition,
        dweller: Dweller,
        request: ExpeditionResolveRequest,
    ) -> SiteRoomView:
        """Own one locked combat turn, including the final reward/defeat and travel-clock update."""
        if request.choice_id is not None:
            raise ValidationException("Combat encounters do not accept a stat-check choice")
        if (
            await crud.expedition_run.get_consumed_for_exploration_site(
                db_session, exploration_id=exploration.id, site_id=site.id
            )
            is not None
        ):
            raise ValidationException(f"{site.name} is already spent for this journey")
        current = run.flags.get("combat") or initial_combat(site)
        if request.expected_round is not None and request.expected_round != current["round"]:
            raise ResourceConflictException("Combat has advanced; refresh the encounter before attacking again")
        state, won, lost, damage = resolve_turn(current, dweller, use_skill=request.use_skill)
        result = BranchResult(damage_taken=damage)
        if won:
            await _pay_reward_vault(exploration, site, full=True, result=result)
            result.texts.insert(0, "Encounter won.")
            exploration.enemies_encountered += len(state["opponents"])
            run.status = ExpeditionRunStatus.CLEARED
        elif lost:
            run.status = ExpeditionRunStatus.DEFEATED
            result.texts.append(
                "Overpowered. The dweller escaped injured, without the site's supplies, and resumed travel."
            )
        else:
            result.texts.append("Combat continues.")
        run.flags = {**run.flags, "combat": state}
        db_session.add(dweller)
        if won or lost:
            run.finished_at = datetime.utcnow()
            from app.services.exploration_service import exploration_service

            exploration_service.resume_from_encounter(exploration)
        # Flush the health mutation before the run row, all within this owner's transaction.
        await db_session.flush([dweller, exploration])
        outcome = result.to_outcome()
        await _log_site_event(db_session, exploration, f"{site.name}: {outcome.text}", health_loss=damage)
        run = await _refresh_run(db_session, run)
        if won:
            vault = await crud.vault.get(db_session, exploration.vault_id)
            await notification_service.create_and_send(
                db_session,
                vault.user_id,
                NotificationType.EXPLORATION_UPDATE,
                "Expedition site cleared",
                f"{dweller.first_name} secured {site.name}. Rewards added to the expedition haul.",
                vault_id=exploration.vault_id,
                from_dweller_id=dweller.id,
                meta_data={"event": "site_cleared", "exploration_id": str(exploration.id), "site_id": site.id},
                commit=False,
            )
        await db_session.commit()
        await notification_service.deliver_deferred_notifications(db_session)
        return build_view(
            exploration.id,
            site,
            run,
            exploration,
            outcome=outcome,
            finale_paid=won,
            defeated=lost,
            dweller=dweller,
        )

    async def retreat_run(self, db_session: AsyncSession, exploration_id: UUID4) -> SiteRoomView:
        """Abandon the run at a room boundary: room loot kept, finale forfeited."""
        exploration = await lock_exploration_with_vault_claim(db_session, exploration_id)
        if not exploration.is_in_progress():
            raise ValidationException("Expedition sites need an active exploration")
        run = await _get_open_run(db_session, exploration_id)
        site = data_loader.get_expedition_site(run.site_id)
        if site is None:
            raise ValidationException(f"Unknown expedition site: {run.site_id!r}")
        run.status = ExpeditionRunStatus.RETREATED
        run.finished_at = datetime.utcnow()
        run = await _refresh_run(db_session, run)

        from app.services.exploration_service import exploration_service

        exploration_service.resume_from_encounter(exploration)
        await _log_site_event(db_session, exploration, f"Retreated from {site.name} with whatever was carried.")
        await db_session.commit()
        dweller_obj = await dweller_crud.get(db_session, exploration.dweller_id)
        return build_view(exploration_id, site, run, exploration, dweller=dweller_obj)


expedition_service = ExpeditionService()
