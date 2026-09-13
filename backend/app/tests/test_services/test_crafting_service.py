"""Tests for instant weapon/outfit crafting."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import JunkTypeEnum, RarityEnum, RoomTypeEnum
from app.core.game_config import game_config
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.room import Room
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.services.crafting_service import crafting_service
from app.utils.exceptions import (
    InsufficientResourcesException,
    ResourceConflictException,
    ValidationException,
)

COMMON_WEAPON = "Pipe pistol"
RARE_WEAPON = "Baseball bat"
COMMON_OUTFIT = "Mechanic jumpsuit"
UNCRAFTABLE_OUTFIT = "RobCo R&D suit"


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
    return room


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


@pytest.mark.asyncio
async def test_list_recipes_reports_costs_and_shortfall(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)

    recipes = await crafting_service.list_recipes(async_session, vault.id, "weapon")

    assert recipes
    pipe_pistol = next(recipe for recipe in recipes if recipe.name == COMMON_WEAPON)
    assert pipe_pistol.junk_cost == game_config.crafting.junk_cost("common")
    assert pipe_pistol.caps_cost == game_config.crafting.caps_cost("common")
    assert pipe_pistol.can_craft is False
    assert pipe_pistol.missing_junk == pipe_pistol.junk_cost


@pytest.mark.asyncio
async def test_list_recipes_excludes_uncraftable_entries(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)

    recipes = await crafting_service.list_recipes(async_session, vault.id, "outfit")

    assert all(recipe.name != UNCRAFTABLE_OUTFIT for recipe in recipes)


@pytest.mark.asyncio
async def test_craft_consumes_junk_and_caps(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, 5)
    await _add_junk(async_session, storage, RarityEnum.RARE, 8)
    vault.bottle_caps = 1_000
    await async_session.commit()

    result = await crafting_service.craft(async_session, vault.id, RARE_WEAPON, "weapon")

    assert result.name == RARE_WEAPON
    assert result.rarity == RarityEnum.RARE
    assert result.junk_spent == game_config.crafting.junk_cost("rare")
    assert result.caps_spent == game_config.crafting.caps_cost("rare")

    crafted = await async_session.get(Weapon, result.item_id)
    assert crafted is not None
    assert crafted.storage_id == storage.id
    assert crafted.damage_min > 0

    rarities = await _junk_rarities(async_session)
    assert len(rarities) == 13 - result.junk_spent
    assert rarities.count(RarityEnum.RARE) == 8 - result.junk_spent
    assert rarities.count(RarityEnum.COMMON) == 5

    refreshed = await crud.vault.get(async_session, vault.id)
    assert refreshed.bottle_caps == 1_000 - result.caps_spent


@pytest.mark.asyncio
async def test_craft_spends_cheapest_eligible_materials_first(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, 2)
    await _add_junk(async_session, storage, RarityEnum.RARE, 6)
    await _add_junk(async_session, storage, RarityEnum.LEGENDARY, 2)
    vault.bottle_caps = 1_000
    await async_session.commit()

    await crafting_service.craft(async_session, vault.id, RARE_WEAPON, "weapon")

    rarities = await _junk_rarities(async_session)
    assert rarities.count(RarityEnum.COMMON) == 2
    assert rarities.count(RarityEnum.RARE) == 0
    assert rarities.count(RarityEnum.LEGENDARY) == 2


@pytest.mark.asyncio
async def test_craft_requires_the_matching_workshop(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Outfit workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, 5)

    with pytest.raises(ValidationException, match="Weapon workshop"):
        await crafting_service.craft(async_session, vault.id, COMMON_WEAPON, "weapon")


@pytest.mark.asyncio
async def test_craft_rejects_uncraftable_item(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Outfit workshop")
    await _add_junk(async_session, storage, RarityEnum.RARE, 10)
    vault.bottle_caps = 1_000
    await async_session.commit()

    with pytest.raises(ValidationException, match="cannot be crafted"):
        await crafting_service.craft(async_session, vault.id, UNCRAFTABLE_OUTFIT, "outfit")


@pytest.mark.asyncio
async def test_craft_rejects_unknown_item(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")

    with pytest.raises(ValidationException, match="Unknown weapon"):
        await crafting_service.craft(async_session, vault.id, "Mystery Blaster", "weapon")


@pytest.mark.asyncio
async def test_craft_insufficient_junk(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, 1)

    with pytest.raises(InsufficientResourcesException):
        await crafting_service.craft(async_session, vault.id, COMMON_WEAPON, "weapon")


@pytest.mark.asyncio
async def test_craft_insufficient_caps(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.RARE, 6)
    vault.bottle_caps = 0
    await async_session.commit()

    with pytest.raises(InsufficientResourcesException):
        await crafting_service.craft(async_session, vault.id, RARE_WEAPON, "weapon")


@pytest.mark.asyncio
async def test_craft_rejects_full_storage(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault, max_space=1)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, 4)

    with pytest.raises(ResourceConflictException):
        await crafting_service.craft(async_session, vault.id, COMMON_WEAPON, "weapon")


@pytest.mark.asyncio
async def test_craft_outfit_lands_in_storage(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Outfit workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, 3)

    result = await crafting_service.craft(async_session, vault.id, COMMON_OUTFIT, "outfit")

    crafted = await async_session.get(Outfit, result.item_id)
    assert crafted is not None
    assert crafted.name == COMMON_OUTFIT
    assert crafted.storage_id == storage.id
