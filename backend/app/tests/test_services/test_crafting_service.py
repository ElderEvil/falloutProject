"""Tests for workshop crafting — recipes and the timed order queue."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum, JunkTypeEnum, RarityEnum, RoomTypeEnum
from app.core.game_config import game_config
from app.models.crafting_order import CraftingOrderStatus
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.room import Room
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.dweller import DwellerCreate
from app.services.crafting_service import crafting_service
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)

COMMON_WEAPON = "Pipe pistol"
RARE_WEAPON = "Baseball bat"
COMMON_OUTFIT = "Mechanic jumpsuit"
UNCRAFTABLE_OUTFIT = "RobCo R&D suit"


def _junk_cost(rarity: RarityEnum) -> int:
    return game_config.crafting.junk_cost(rarity.value)


def _caps_cost(rarity: RarityEnum) -> int:
    return game_config.crafting.caps_cost(rarity.value)


async def _make_storage(async_session: AsyncSession, vault: Vault, max_space: int = 100) -> Storage:
    storage = Storage(vault_id=vault.id, max_space=max_space)
    async_session.add(storage)
    await async_session.commit()
    await async_session.refresh(storage)
    return storage


async def _add_workshop(async_session: AsyncSession, vault: Vault, name: str) -> Room:
    room = Room(
        name=name,
        category=RoomTypeEnum.CRAFTING,
        ability=None,
        population_required=None,
        base_cost=800,
        incremental_cost=600,
        t2_upgrade_cost=8000,
        t3_upgrade_cost=60000,
        size_min=9,
        size_max=9,
        size=9,
        tier=1,
        coordinate_x=0,
        coordinate_y=0,
        image_url=None,
        vault_id=vault.id,
    )
    async_session.add(room)
    await async_session.commit()
    await async_session.refresh(room)
    return room


async def _add_worker(async_session: AsyncSession, vault: Vault, room: Room, index: int = 0) -> Dweller:
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            first_name=f"Worker{index}",
            last_name="Test",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            level=1,
            experience=0,
            max_health=100,
            health=100,
            radiation=0,
            happiness=50,
            strength=5,
            perception=5,
            endurance=5,
            charisma=5,
            intelligence=5,
            agility=5,
            luck=5,
            vault_id=vault.id,
        ),
    )
    # room_id is not part of the create schema; assign it like the breeding path does.
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


async def _add_junk(async_session: AsyncSession, storage: Storage, rarity: RarityEnum, count: int) -> None:
    for index in range(count):
        async_session.add(
            Junk(
                name=f"Steel {rarity.value}{index}",
                junk_type=JunkTypeEnum.STEEL,
                rarity=rarity,
                value=game_config.exploration.get_junk_value(rarity.value),
                description="Test material",
                storage_id=storage.id,
            )
        )
    await async_session.commit()


async def _junk_rarities(async_session: AsyncSession) -> list[RarityEnum]:
    rows = (await async_session.execute(select(Junk))).scalars().all()
    return sorted(RarityEnum(row.rarity) for row in rows)


async def _finish_queue(async_session: AsyncSession, vault_id) -> None:
    """Force every active order past its completion time and run the tick."""
    for order in await crud.crafting_order.get_active_by_vault(async_session, vault_id):
        order.estimated_completion_at = datetime.utcnow() - timedelta(seconds=1)
        async_session.add(order)
    await async_session.commit()
    await crafting_service.advance_orders(async_session, vault_id)


@pytest.mark.asyncio
async def test_list_recipes_reports_costs_and_shortfall(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)

    recipes = await crafting_service.list_recipes(async_session, vault.id, "weapon")

    assert recipes
    pipe_pistol = next(recipe for recipe in recipes if recipe.name == COMMON_WEAPON)
    assert pipe_pistol.junk_cost == _junk_cost(RarityEnum.COMMON)
    assert pipe_pistol.caps_cost == _caps_cost(RarityEnum.COMMON)
    assert pipe_pistol.can_craft is False
    assert pipe_pistol.missing_junk == pipe_pistol.junk_cost


@pytest.mark.asyncio
async def test_list_recipes_marks_craftable_with_enough_materials(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))

    recipes = await crafting_service.list_recipes(async_session, vault.id, "weapon")

    pipe_pistol = next(recipe for recipe in recipes if recipe.name == COMMON_WEAPON)
    assert pipe_pistol.can_craft is True
    assert pipe_pistol.missing_junk == 0


@pytest.mark.asyncio
async def test_list_recipes_excludes_uncraftable_entries(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)

    recipes = await crafting_service.list_recipes(async_session, vault.id, "outfit")

    assert all(recipe.name != UNCRAFTABLE_OUTFIT for recipe in recipes)


@pytest.mark.asyncio
async def test_catalog_entries_without_craftable_flag_are_excluded(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The flag is opt-in: an entry that never opted in is neither listed nor queued."""
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))

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

    async def fake_catalog(_item_type: str) -> list[dict]:
        return [unflagged]

    monkeypatch.setattr(crafting_service, "_catalog", fake_catalog)

    assert await crafting_service.list_recipes(async_session, vault.id, "weapon") == []
    with pytest.raises(ValidationException, match="cannot be crafted"):
        await crafting_service.start_order(async_session, vault.id, "Pipe pistol", "weapon")


@pytest.mark.asyncio
async def test_start_order_consumes_materials_and_caps(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    common_count = _junk_cost(RarityEnum.COMMON)
    rare_count = _junk_cost(RarityEnum.RARE) + 2
    await _add_junk(async_session, storage, RarityEnum.COMMON, common_count)
    await _add_junk(async_session, storage, RarityEnum.RARE, rare_count)
    vault.bottle_caps = 1_000
    await async_session.commit()

    order = await crafting_service.start_order(async_session, vault.id, RARE_WEAPON, "weapon")

    assert order.status == CraftingOrderStatus.ACTIVE
    assert order.item_name == RARE_WEAPON
    assert order.junk_spent == _junk_cost(RarityEnum.RARE)
    assert order.caps_spent == _caps_cost(RarityEnum.RARE)
    assert order.progress == 0.0
    assert order.estimated_completion_at > order.started_at

    rarities = await _junk_rarities(async_session)
    assert len(rarities) == common_count + rare_count - order.junk_spent
    assert rarities.count(RarityEnum.COMMON) == common_count
    assert rarities.count(RarityEnum.RARE) == rare_count - order.junk_spent

    refreshed = await crud.vault.get(async_session, vault.id)
    assert refreshed.bottle_caps == 1_000 - order.caps_spent


@pytest.mark.asyncio
async def test_start_order_spends_cheapest_eligible_materials_first(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    rare_cost = _junk_cost(RarityEnum.RARE)
    await _add_junk(async_session, storage, RarityEnum.COMMON, rare_cost)
    await _add_junk(async_session, storage, RarityEnum.RARE, rare_cost)
    await _add_junk(async_session, storage, RarityEnum.LEGENDARY, 2)
    vault.bottle_caps = 1_000
    await async_session.commit()

    await crafting_service.start_order(async_session, vault.id, RARE_WEAPON, "weapon")

    rarities = await _junk_rarities(async_session)
    assert rarities.count(RarityEnum.COMMON) == rare_cost
    assert rarities.count(RarityEnum.RARE) == 0
    assert rarities.count(RarityEnum.LEGENDARY) == 2


@pytest.mark.asyncio
async def test_start_order_requires_the_matching_workshop(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Outfit workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))

    with pytest.raises(ValidationException, match="Weapon workshop"):
        await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")


@pytest.mark.asyncio
async def test_start_order_rejects_uncraftable_item(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Outfit workshop")
    await _add_junk(async_session, storage, RarityEnum.RARE, _junk_cost(RarityEnum.RARE))
    vault.bottle_caps = 1_000
    await async_session.commit()

    with pytest.raises(ValidationException, match="cannot be crafted"):
        await crafting_service.start_order(async_session, vault.id, UNCRAFTABLE_OUTFIT, "outfit")


@pytest.mark.asyncio
async def test_start_order_rejects_unknown_item(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")

    with pytest.raises(ValidationException, match="Unknown weapon"):
        await crafting_service.start_order(async_session, vault.id, "Mystery Blaster", "weapon")


@pytest.mark.asyncio
async def test_start_order_insufficient_junk(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON) - 1)

    with pytest.raises(InsufficientResourcesException):
        await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")


@pytest.mark.asyncio
async def test_start_order_insufficient_caps(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.RARE, _junk_cost(RarityEnum.RARE))
    vault.bottle_caps = 0
    await async_session.commit()

    with pytest.raises(InsufficientResourcesException):
        await crafting_service.start_order(async_session, vault.id, RARE_WEAPON, "weapon")


@pytest.mark.asyncio
async def test_workers_shorten_the_order_duration(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    room = await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON) * 2)

    unstaffed = crafting_service.order_duration_seconds(RarityEnum.COMMON, 0)

    solo = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    solo_seconds = (solo.estimated_completion_at - solo.started_at).total_seconds()
    assert solo.workers_at_start == 0
    assert solo_seconds == unstaffed

    await _add_worker(async_session, vault, room)
    await _add_worker(async_session, vault, room, index=1)

    staffed = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    staffed_seconds = (staffed.estimated_completion_at - staffed.started_at).total_seconds()

    assert staffed.workers_at_start == 2
    assert staffed_seconds < solo_seconds


@pytest.mark.asyncio
async def test_advance_orders_completes_finished_orders(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")

    assert await crafting_service.advance_orders(async_session, vault.id) == 0

    await _finish_queue(async_session, vault.id)

    await async_session.refresh(order)
    assert order.status == CraftingOrderStatus.COMPLETED
    assert order.progress == 1.0
    assert order.completed_at is not None
    assert await crafting_service.advance_orders(async_session, vault.id) == 0


@pytest.mark.asyncio
async def test_collect_order_grants_the_item(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")
    await _finish_queue(async_session, vault.id)

    result = await crafting_service.collect_order(async_session, vault.id, order.id)

    crafted = await async_session.get(Weapon, result.item_id)
    assert crafted is not None
    assert crafted.storage_id == storage.id
    assert result.junk_spent == _junk_cost(RarityEnum.COMMON)

    await async_session.refresh(order)
    assert order.status == CraftingOrderStatus.COLLECTED


@pytest.mark.asyncio
async def test_collect_order_requires_a_finished_order(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))
    order = await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")

    with pytest.raises(ValidationException, match="not ready"):
        await crafting_service.collect_order(async_session, vault.id, order.id)


@pytest.mark.asyncio
async def test_collect_order_unknown_order(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")

    with pytest.raises(ResourceNotFoundException):
        await crafting_service.collect_order(async_session, vault.id, uuid4())


@pytest.mark.asyncio
async def test_collect_order_rejects_full_storage(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault, max_space=1)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))
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


@pytest.mark.asyncio
async def test_collect_order_outfit_lands_in_storage(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Outfit workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))
    order = await crafting_service.start_order(async_session, vault.id, COMMON_OUTFIT, "outfit")
    await _finish_queue(async_session, vault.id)

    result = await crafting_service.collect_order(async_session, vault.id, order.id)

    crafted = await async_session.get(Outfit, result.item_id)
    assert crafted is not None
    assert crafted.name == COMMON_OUTFIT
    assert crafted.storage_id == storage.id


@pytest.mark.asyncio
async def test_list_orders_returns_the_queue(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, _junk_cost(RarityEnum.COMMON))
    await crafting_service.start_order(async_session, vault.id, COMMON_WEAPON, "weapon")

    orders = await crafting_service.list_orders(async_session, vault.id)

    assert [order.item_name for order in orders] == [COMMON_WEAPON]
