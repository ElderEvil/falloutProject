from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import CraftingOrderStatus, GenderEnum, JunkTypeEnum, NotificationType, RarityEnum, RoomTypeEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.notification import Notification
from app.models.outfit import Outfit
from app.models.room import Room
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.dweller import DwellerCreate
from app.services.crafting_service import crafting_service
from app.services.game_tick import crafting_tick
from app.services.recipe_unlock_service import recipe_unlock_service
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.utils.time import utcnow

COMMON_WEAPON = "Pipe pistol"
RARE_WEAPON = "Baseball bat"
COMMON_OUTFIT = "Mechanic jumpsuit"
UNCRAFTABLE_OUTFIT = "RobCo R&D suit"
THEME_WORKSHOP = "Theme workshop"
PARTY_THEME = "Party theme"
WEAPON_SHOP = "Weapon workshop"


def _cadence_tick() -> dict[str, int]:
    tick = game_config.game_loop.tick_interval
    return {"total_game_time": settings.CRAFTING_ADVANCE_EVERY_N_TICKS * tick, "seconds_passed": tick}


def _junk_cost(rarity: RarityEnum) -> int:
    return game_config.crafting.junk_cost(rarity.value)


def _caps_cost(rarity: RarityEnum) -> int:
    return game_config.crafting.caps_cost(rarity.value)


COMMON_JUNK = _junk_cost(RarityEnum.COMMON)
RARE_JUNK = _junk_cost(RarityEnum.RARE)


async def _unlock_weapon(async_session, vault, name) -> None:
    await recipe_unlock_service.record_scrap(async_session, vault_id=vault.id, item_type="weapon", item_name=name)
    await async_session.commit()


async def _make_storage(async_session, vault, max_space: int = 100) -> Storage:
    storage = Storage(vault_id=vault.id, max_space=max_space)
    async_session.add(storage)
    await async_session.commit()
    await async_session.refresh(storage)
    return storage


async def _add_workshop(async_session, vault, name, category: RoomTypeEnum = RoomTypeEnum.CRAFTING) -> Room:
    room = Room(
        name=name,
        category=category,
        ability=None,
        base_cost=800,
        incremental_cost=600,
        t2_upgrade_cost=8000,
        t3_upgrade_cost=60000,
        size_min=9,
        size_max=9,
        size=9,
        coordinate_x=0,
        coordinate_y=0,
        vault_id=vault.id,
    )
    async_session.add(room)
    await async_session.commit()
    await async_session.refresh(room)
    return room


SPECIAL = {"strength": 5, "perception": 5, "endurance": 5, "charisma": 5, "intelligence": 5, "agility": 5, "luck": 5}
WORKER = {"last_name": "Test", "gender": GenderEnum.MALE, "rarity": RarityEnum.COMMON, "max_health": 100, "health": 100}


async def _add_worker(async_session, vault, room: Room, index: int = 0, **stats: int) -> Dweller:
    payload = WORKER | SPECIAL | stats | {"first_name": f"Worker{index}"}
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**payload, vault_id=vault.id))
    # room_id is not part of the create schema; assign it like the breeding path does.
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


async def _add_junk(session, storage: Storage, rarity: RarityEnum, count: int, junk_type=JunkTypeEnum.STEEL) -> None:
    value = game_config.exploration.get_junk_value(rarity.value)
    session.add_all(
        Junk(
            name=f"{junk_type.value[:6]}{rarity.value}{index}",
            junk_type=junk_type,
            rarity=rarity,
            value=value,
            description="Test material",
            storage_id=storage.id,
        )
        for index in range(count)
    )
    await session.commit()


async def _ready(
    async_session,
    vault,
    junk: Sequence[tuple] = (),
    *,
    workshop: str = WEAPON_SHOP,
    category: RoomTypeEnum = RoomTypeEnum.CRAFTING,
    max_space: int = 100,
    caps: int | None = None,
) -> tuple[Storage, Room]:
    storage = await _make_storage(async_session, vault, max_space)
    room = await _add_workshop(async_session, vault, workshop, category)
    for entry in junk:
        await _add_junk(async_session, storage, *entry)
    if caps is not None:
        vault.bottle_caps = caps
        await async_session.commit()
    return storage, room


async def _weapon(async_session, vault, count: int | None = None, *, max_space: int = 100) -> tuple[Storage, Room]:
    return await _ready(
        async_session, vault, [(RarityEnum.COMMON, COMMON_JUNK if count is None else count)], max_space=max_space
    )


async def _rare(async_session, vault, count: int | None = None, *, caps: int | None = None) -> tuple[Storage, Room]:
    junk = [(RarityEnum.RARE, RARE_JUNK if count is None else count)]
    storage, room = await _ready(async_session, vault, junk, caps=caps)
    await _unlock_weapon(async_session, vault, RARE_WEAPON)
    return storage, room


async def _theme(async_session, vault, count: int | None = None, *, caps: int | None = None) -> tuple[Storage, Room]:
    junk = [(RarityEnum.COMMON, COMMON_JUNK if count is None else count, JunkTypeEnum.CLOTH)]
    return await _ready(async_session, vault, junk, workshop=THEME_WORKSHOP, category=RoomTypeEnum.THEME, caps=caps)


async def _junk_rarities(async_session) -> list[RarityEnum]:
    rows = (await async_session.execute(select(Junk))).scalars().all()
    return sorted(RarityEnum(row.rarity) for row in rows)


async def _finish_queue(async_session, vault_id) -> None:
    for order in await crud.crafting_order.get_active_by_vault(async_session, vault_id):
        order.estimated_completion_at = utcnow() - timedelta(seconds=1)
        async_session.add(order)
    await async_session.commit()
    await crafting_service.advance_orders(async_session, vault_id)


async def _collect(async_session, vault, name, item_type: str):
    order = await crafting_service.start_order(async_session, vault.id, name, item_type)
    await _finish_queue(async_session, vault.id)
    return order, await crafting_service.collect_order(async_session, vault.id, order.id)


async def test_list_recipes_reports_costs_shortfall_and_craftability(async_session, vault) -> None:
    storage = await _make_storage(async_session, vault)
    outfits = await crafting_service.list_recipes(async_session, vault.id, "outfit")
    assert all(recipe.name != UNCRAFTABLE_OUTFIT for recipe in outfits)
    recipes = await crafting_service.list_recipes(async_session, vault.id, "weapon")
    assert recipes
    pipe_pistol = next(recipe for recipe in recipes if recipe.name == COMMON_WEAPON)
    assert pipe_pistol.junk_cost == COMMON_JUNK
    assert pipe_pistol.caps_cost == _caps_cost(RarityEnum.COMMON)
    assert pipe_pistol.can_craft is False
    assert pipe_pistol.missing_junk == pipe_pistol.junk_cost
    await _add_junk(async_session, storage, RarityEnum.COMMON, COMMON_JUNK)
    recipes = await crafting_service.list_recipes(async_session, vault.id, "weapon")
    pipe_pistol = next(recipe for recipe in recipes if recipe.name == COMMON_WEAPON)
    assert pipe_pistol.can_craft is True
    assert pipe_pistol.missing_junk == 0


@pytest.mark.parametrize(
    ("name", "junk_types"),
    [("Vault 33 suit", ["cloth", "valuables"]), ("BOS casual", ["cloth", "leather"])],
)
async def test_power_struggle_outfits_craftable_without_discovery(async_session, vault, name, junk_types) -> None:
    mats = [(RarityEnum(r), c, JunkTypeEnum.CLOTH) for r, c in game_config.crafting.junk_recipe("rare").items()]
    storage, _ = await _ready(async_session, vault, mats, workshop="Outfit workshop", caps=1_000)
    recipes = await crafting_service.list_recipes(async_session, vault.id, "outfit")
    recipe = next((recipe for recipe in recipes if recipe.name == name), None)
    assert recipe is not None
    assert recipe.unlocked is True
    assert recipe.can_craft is True
    assert (recipe.junk_types, recipe.rarity) == (junk_types, RarityEnum.RARE)
    _, result = await _collect(async_session, vault, name, "outfit")
    outfit = await async_session.get(Outfit, result.item_id)
    assert outfit is not None
    assert (outfit.name, outfit.rarity) == (name, RarityEnum.RARE)
    assert outfit.storage_id == storage.id


async def test_catalog_entries_without_craftable_flag_are_excluded(async_session, vault, monkeypatch) -> None:
    await _weapon(async_session, vault)
    unflagged = {
        "name": "Pipe pistol",
        "rarity": "Common",
        "weapon_type": "Gun",
        "weapon_subtype": "Pistol",
        "stat": "agility",
        "damage_min": 1,
        "damage_max": 3,
        "value": 10,
    }

    def fake_catalog(_item_type: str) -> list[dict]:
        return [unflagged]

    monkeypatch.setattr(crafting_service, "_catalog", fake_catalog)
    assert await crafting_service.list_recipes(async_session, vault.id, "weapon") == []
    with pytest.raises(ValidationException, match="cannot be crafted"):
        await crafting_service.start_order(async_session, vault.id, "Pipe pistol", "weapon")


async def test_start_order_consumes_materials_and_caps(async_session, vault) -> None:
    recipe = game_config.crafting.junk_recipe("rare")
    common_count, rare_count = recipe["common"] + 2, recipe["rare"] + 2
    await _ready(async_session, vault, [(RarityEnum.COMMON, common_count), (RarityEnum.RARE, rare_count)], caps=1_000)
    await _unlock_weapon(async_session, vault, RARE_WEAPON)
    order = await crafting_service.start_order(async_session, vault.id, RARE_WEAPON, "weapon")
    assert (order.status, order.item_name) == (CraftingOrderStatus.ACTIVE, RARE_WEAPON)
    assert order.junk_spent == game_config.crafting.junk_cost("rare")
    assert order.caps_spent == _caps_cost(RarityEnum.RARE)
    assert order.progress == 0.0
    assert order.estimated_completion_at > order.started_at
    rarities = await _junk_rarities(async_session)
    assert rarities.count(RarityEnum.COMMON) == common_count - recipe["common"]
    assert rarities.count(RarityEnum.RARE) == rare_count - recipe["rare"]
    refreshed = await crud.vault.get(async_session, vault.id)
    assert refreshed.bottle_caps == 1_000 - order.caps_spent


async def test_only_the_items_junk_types_count(async_session, vault) -> None:
    circuits = [(RarityEnum.COMMON, 10, JunkTypeEnum.CIRCUITRY), (RarityEnum.RARE, 10, JunkTypeEnum.CIRCUITRY)]
    await _ready(async_session, vault, circuits)
    await _unlock_weapon(async_session, vault, RARE_WEAPON)
    with pytest.raises(InsufficientResourcesException):
        await crafting_service.start_order(async_session, vault.id, RARE_WEAPON, "weapon")


async def test_each_tier_needs_its_own_rarity(async_session, vault) -> None:
    await _rare(async_session, vault, count=10)
    with pytest.raises(InsufficientResourcesException):
        await crafting_service.start_order(async_session, vault.id, RARE_WEAPON, "weapon")


async def test_recipe_reports_stock_and_projected_time(async_session, vault) -> None:
    _, room = await _weapon(async_session, vault, count=5)
    await _add_worker(async_session, vault, room, agility=8)
    recipes = await crafting_service.list_recipes(async_session, vault.id, "weapon")
    pipe_pistol = next(recipe for recipe in recipes if recipe.name == COMMON_WEAPON)
    assert pipe_pistol.junk_types == ["circuitry", "steel"]
    assert (pipe_pistol.junk_materials, pipe_pistol.available_junk) == ({"common": 3}, {"common": 5})
    assert pipe_pistol.ability_sum == 8
    assert pipe_pistol.duration_seconds == crafting_service.order_duration_seconds(RarityEnum.COMMON, 8)
    assert pipe_pistol.duration_seconds < crafting_service.order_duration_seconds(RarityEnum.COMMON, 0)


@pytest.mark.parametrize(
    ("workshop", "item", "kind", "match"),
    [
        (None, PARTY_THEME, "theme", "Build the Theme workshop"),
        ("Outfit workshop", COMMON_WEAPON, "weapon", "Weapon workshop"),
    ],
)
async def test_start_order_requires_the_matching_workshop(async_session, vault, workshop, item, kind, match) -> None:
    if workshop is None:
        await _make_storage(async_session, vault)
    else:
        await _ready(async_session, vault, [(RarityEnum.COMMON, COMMON_JUNK)], workshop=workshop)
    with pytest.raises(ValidationException, match=match):
        await crafting_service.start_order(async_session, vault.id, item, kind)


@pytest.mark.parametrize(
    ("item", "kind", "match"),
    [(UNCRAFTABLE_OUTFIT, "outfit", "cannot be crafted"), ("Mystery Blaster", "weapon", "Unknown weapon")],
)
async def test_start_order_rejects_uncraftable_or_unknown_items(async_session, vault, item, kind, match) -> None:
    if kind == "outfit":
        await _ready(async_session, vault, [(RarityEnum.RARE, RARE_JUNK)], workshop="Outfit workshop", caps=1_000)
    else:
        await _ready(async_session, vault)
    with pytest.raises(ValidationException, match=match):
        await crafting_service.start_order(async_session, vault.id, item, kind)


@pytest.mark.parametrize(("count", "caps", "item"), [(COMMON_JUNK - 1, None, COMMON_WEAPON), (None, 0, RARE_WEAPON)])
async def test_start_order_insufficient_materials_or_caps(async_session, vault, count, caps, item) -> None:
    if count is None:
        await _rare(async_session, vault, caps=caps)
    else:
        await _weapon(async_session, vault, count=count)
    with pytest.raises(InsufficientResourcesException):
        await crafting_service.start_order(async_session, vault.id, item, "weapon")


async def test_item_stat_shortens_the_order_duration(async_session, vault) -> None:
    _, room = await _weapon(async_session, vault, count=COMMON_JUNK * 2)
    unstaffed = crafting_service.order_duration_seconds(RarityEnum.COMMON, 0)
    solo = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    solo_seconds = (solo.estimated_completion_at - solo.started_at).total_seconds()
    assert (solo.required_stat, solo.ability_sum_at_start) == ("agility", 0)
    assert solo_seconds == unstaffed
    await _add_worker(async_session, vault, room, agility=7)
    await _add_worker(async_session, vault, room, index=1, agility=7)
    staffed = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    staffed_seconds = (staffed.estimated_completion_at - staffed.started_at).total_seconds()
    assert staffed.ability_sum_at_start == 14
    assert staffed_seconds < solo_seconds
    assert staffed_seconds == crafting_service.order_duration_seconds(RarityEnum.COMMON, 14)


async def test_unrelated_stats_do_not_speed_the_craft(async_session, vault) -> None:
    _, room = await _weapon(async_session, vault)
    await _add_worker(async_session, vault, room, strength=10, agility=1)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    assert (order.required_stat, order.ability_sum_at_start) == ("agility", 1)


async def test_advance_orders_completes_finished_orders(async_session, vault) -> None:
    await _weapon(async_session, vault)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    assert await crafting_service.advance_orders(async_session, vault.id) == 0
    await _finish_queue(async_session, vault.id)
    await async_session.refresh(order)
    assert (order.status, order.progress) == (CraftingOrderStatus.COMPLETED, 1.0)
    assert order.completed_at is not None
    assert await crafting_service.advance_orders(async_session, vault.id) == 0


@pytest.mark.parametrize(
    ("item", "kind", "model", "junk_type", "workshop"),
    [
        (COMMON_WEAPON, "weapon", Weapon, JunkTypeEnum.STEEL, WEAPON_SHOP),
        (COMMON_OUTFIT, "outfit", Outfit, JunkTypeEnum.CLOTH, "Outfit workshop"),
    ],
)
async def test_collect_order_grants_the_item(async_session, vault, item, kind, model, junk_type, workshop) -> None:
    storage, _ = await _ready(async_session, vault, [(RarityEnum.COMMON, COMMON_JUNK, junk_type)], workshop=workshop)
    order, result = await _collect(async_session, vault, item, kind)
    crafted = await async_session.get(model, result.item_id)
    assert crafted is not None
    assert (crafted.name, crafted.storage_id) == (item, storage.id)
    assert result.junk_spent == COMMON_JUNK
    await async_session.refresh(order)
    assert order.status == CraftingOrderStatus.COLLECTED


async def test_collect_order_requires_a_finished_order(async_session, vault) -> None:
    await _weapon(async_session, vault)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    with pytest.raises(ValidationException, match="not ready"):
        await crafting_service.collect_order(async_session, vault.id, order.id)


@pytest.mark.parametrize("method", ["collect_order", "cancel_order"])
async def test_unknown_order_id_raises_not_found(async_session, vault, method) -> None:
    with pytest.raises(ResourceNotFoundException):
        await getattr(crafting_service, method)(async_session, vault.id, uuid4())


async def test_collect_order_rejects_full_storage(async_session, vault) -> None:
    storage, _ = await _weapon(async_session, vault, max_space=1)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    async_session.add(
        Weapon(
            name="Spare gun",
            rarity=RarityEnum.COMMON,
            weapon_type="gun",
            weapon_subtype="pistol",
            stat="agility",
            damage_min=1,
            damage_max=3,
            value=5,
            storage_id=storage.id,
        )
    )
    await async_session.commit()
    await _finish_queue(async_session, vault.id)
    with pytest.raises(ResourceConflictException):
        await crafting_service.collect_order(async_session, vault.id, order.id)


async def test_list_orders_returns_the_queue(async_session, vault) -> None:
    await _weapon(async_session, vault)
    await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    orders = await crafting_service.list_orders(async_session, vault.id)
    assert [order.item_name for order in orders] == [COMMON_WEAPON]


async def test_crafting_tick_detects_completion_only_on_a_cadence_boundary(async_session, vault) -> None:
    # The cadence delays detection, never the order's wall-clock completion time; the tick that does
    # detect it notifies the owner.
    await _weapon(async_session, vault)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    order.estimated_completion_at = utcnow() - timedelta(seconds=1)
    async_session.add(order)
    await async_session.commit()
    completion_at = order.estimated_completion_at
    due = _cadence_tick()
    off_cadence = due["total_game_time"] - due["seconds_passed"]
    skipped = await crafting_tick.process_crafting(
        async_session, vault.id, total_game_time=off_cadence, seconds_passed=due["seconds_passed"]
    )
    assert skipped == {"completed": 0}
    await async_session.refresh(order)
    assert (order.status, order.estimated_completion_at) == (CraftingOrderStatus.ACTIVE, completion_at)
    completed = await crafting_tick.process_crafting(async_session, vault.id, **due)
    assert completed == {"completed": 1}
    await async_session.refresh(order)
    assert (order.status, order.estimated_completion_at) == (CraftingOrderStatus.COMPLETED, completion_at)
    result = await async_session.execute(select(Notification).where(Notification.vault_id == vault.id))
    assert any(n.notification_type == NotificationType.CRAFTING_COMPLETE for n in result.scalars().all())


async def test_theme_recipes_are_listed_unowned_until_crafted(async_session, vault) -> None:
    await _make_storage(async_session, vault)
    recipes = await crafting_service.list_recipes(async_session, vault.id, "theme")
    assert len(recipes) == 8
    party = next(recipe for recipe in recipes if recipe.name == PARTY_THEME)
    assert party.style == "party"
    assert party.unlocked is True
    assert party.owned is False


async def test_collecting_a_theme_order_grants_vault_ownership(async_session, vault) -> None:
    await _theme(async_session, vault)
    _, result = await _collect(async_session, vault, PARTY_THEME, "theme")
    assert result.item_type == "theme"
    assert result.item_id is None
    assert await crud.vault_theme.is_crafted(async_session, vault.id, "party")


@pytest.mark.parametrize(("collected", "match"), [(True, "already been crafted"), (False, "already being crafted")])
async def test_a_theme_cannot_be_crafted_twice(async_session, vault, collected, match) -> None:
    await _theme(async_session, vault, count=COMMON_JUNK + 3)
    order = await crafting_service.start_order(async_session, vault.id, PARTY_THEME, "theme")
    if collected:
        await _finish_queue(async_session, vault.id)
        await crafting_service.collect_order(async_session, vault.id, order.id)
    with pytest.raises(ValidationException, match=match):
        await crafting_service.start_order(async_session, vault.id, PARTY_THEME, "theme")


async def test_collecting_a_theme_needs_no_storage_space(async_session, vault) -> None:
    storage, _ = await _theme(async_session, vault)
    order = await crafting_service.start_order(async_session, vault.id, PARTY_THEME, "theme")
    await async_session.delete(storage)
    await async_session.commit()
    await _finish_queue(async_session, vault.id)
    result = await crafting_service.collect_order(async_session, vault.id, order.id)
    assert result.name == PARTY_THEME


async def test_boosted_seeding_crafts_every_theme(async_session, vault) -> None:
    from app.services.catalog_service import load_themes
    from app.services.vault import seeding

    await seeding.seed_boosted_theme_unlocks(async_session, vault.id)
    crafted = await crud.vault_theme.crafted_styles(async_session, vault.id)
    assert crafted == {str(entry["style"]) for entry in load_themes()}


async def test_theme_duration_shortens_with_matching_crew(async_session, vault) -> None:
    _, workshop = await _theme(async_session, vault)

    async def party_recipe():
        recipes = await crafting_service.list_recipes(async_session, vault.id, "theme")
        return next(recipe for recipe in recipes if recipe.name == PARTY_THEME)

    base_party = await party_recipe()
    await _add_worker(async_session, vault, workshop, index=1, agility=10)
    await _add_worker(async_session, vault, workshop, index=2, agility=10)
    party = await party_recipe()
    assert party.ability_sum == 20
    assert party.duration_seconds < base_party.duration_seconds
    order = await crafting_service.start_order(async_session, vault.id, PARTY_THEME, "theme")
    assert (order.estimated_completion_at - order.started_at).total_seconds() == party.duration_seconds


async def test_cancel_active_order_refunds_caps_and_junk(async_session, vault) -> None:
    storage, _ = await _theme(async_session, vault, caps=1_000)
    await _add_junk(async_session, storage, RarityEnum.RARE, 3, JunkTypeEnum.CLOTH)
    order = await crafting_service.start_order(async_session, vault.id, "Halloween theme", "theme")
    cancelled = await crafting_service.cancel_order(async_session, vault.id, order.id)
    assert cancelled.status == CraftingOrderStatus.CANCELLED
    assert cancelled.cancelled_at is not None
    assert await crud.crafting_order.get_active_by_vault(async_session, vault.id) == []
    refreshed_vault = await crud.vault.get(async_session, vault.id)
    assert refreshed_vault.bottle_caps == 1_000
    junk = (await async_session.execute(select(Junk))).scalars().all()
    assert len(junk) == 6


async def test_cancel_rejects_orders_that_are_not_active(async_session, vault) -> None:
    await _weapon(async_session, vault)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    await _finish_queue(async_session, vault.id)
    with pytest.raises(ValidationException, match="Only active orders"):
        await crafting_service.cancel_order(async_session, vault.id, order.id)


async def test_cancelled_theme_can_be_queued_again(async_session, vault) -> None:
    await _theme(async_session, vault)
    order = await crafting_service.start_order(async_session, vault.id, PARTY_THEME, "theme")
    await crafting_service.cancel_order(async_session, vault.id, order.id)
    replacement = await crafting_service.start_order(async_session, vault.id, PARTY_THEME, "theme")
    assert replacement.id != order.id


async def test_cancel_legacy_order_rebuilds_an_equivalent_junk_refund(async_session, vault) -> None:
    await _theme(async_session, vault)
    order = await crafting_service.start_order(async_session, vault.id, PARTY_THEME, "theme")
    order.junk_snapshot = []
    async_session.add(order)
    await async_session.commit()
    await crafting_service.cancel_order(async_session, vault.id, order.id)
    junk = (await async_session.execute(select(Junk))).scalars().all()
    assert len(junk) == COMMON_JUNK


async def test_crafting_tick_does_not_revive_a_cancelled_order(async_session, vault) -> None:
    await _weapon(async_session, vault)
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    await crafting_service.cancel_order(async_session, vault.id, order.id)
    order.estimated_completion_at = utcnow() - timedelta(seconds=1)
    async_session.add(order)
    await async_session.commit()
    stats = await crafting_tick.process_crafting(async_session, vault.id, **_cadence_tick())
    assert stats["completed"] == 0
    await async_session.refresh(order)
    assert order.status == CraftingOrderStatus.CANCELLED
