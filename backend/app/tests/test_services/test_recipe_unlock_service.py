"""Tests for learning gated crafting recipes by scrapping the exact item (v1)."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RarityEnum
from app.core.game_config import game_config
from app.models.vault import Vault
from app.services.crafting_service import crafting_service
from app.services.recipe_unlock_service import (
    catalog_entry,
    is_gated,
    recipe_unlock_service,
    scrap_unlock_count,
    unlock_hint,
)
from app.tests.test_services.test_crafting_service import _add_junk, _add_workshop, _make_storage
from app.utils.exceptions import InsufficientResourcesException, ValidationException

LEGENDARY_WEAPON = "Power fist"
COMMON_WEAPON = "Pipe pistol"
RARE_WEAPON = "Baseball bat"


def test_rare_and_legendary_recipes_are_gated_by_default():
    rare = catalog_entry("weapon", RARE_WEAPON)
    assert rare is not None
    assert scrap_unlock_count(rare) == game_config.crafting.scrap_unlock_count("rare") == 1
    assert is_gated(rare) is True

    legendary = catalog_entry("weapon", LEGENDARY_WEAPON)
    assert legendary is not None
    assert scrap_unlock_count(legendary) == game_config.crafting.scrap_unlock_count("legendary") == 1
    assert is_gated(legendary) is True

    assert is_gated(catalog_entry("weapon", COMMON_WEAPON)) is False


def test_unlock_hint_names_the_exact_item():
    assert (
        unlock_hint(catalog_entry("weapon", RARE_WEAPON)) == "Scrap a Baseball bat to reverse-engineer this schematic"
    )
    assert (
        unlock_hint(catalog_entry("weapon", LEGENDARY_WEAPON))
        == "Scrap a Power fist to reverse-engineer this schematic"
    )
    assert unlock_hint(catalog_entry("weapon", COMMON_WEAPON)) is None
    assert unlock_hint(None) is None


def test_catalog_override_beats_the_rarity_default():
    entry = {"rarity": "common", "craft": {"unlock": {"scrap": {"count": 5}}}}
    assert scrap_unlock_count(entry) == 5
    assert is_gated(entry) is True


def test_catalog_entry_matching_ignores_case_and_whitespace():
    assert catalog_entry("weapon", f"  {LEGENDARY_WEAPON.upper()}  ") is not None
    assert catalog_entry("outfit", LEGENDARY_WEAPON) is None
    assert catalog_entry("weapon", "") is None
    assert is_gated(None) is False


@pytest.mark.asyncio
async def test_scrapping_a_gated_item_unlocks_its_recipe(async_session: AsyncSession, vault: Vault) -> None:
    entry = catalog_entry("weapon", RARE_WEAPON)
    assert not await recipe_unlock_service.is_unlocked(
        async_session, vault_id=vault.id, item_type="weapon", entry=entry
    )

    unlocked = await recipe_unlock_service.record_scrap(
        async_session, vault_id=vault.id, item_type="weapon", item_name=RARE_WEAPON
    )
    await async_session.commit()

    assert unlocked == {"item_type": "weapon", "recipe_name": RARE_WEAPON}
    assert await recipe_unlock_service.is_unlocked(async_session, vault_id=vault.id, item_type="weapon", entry=entry)
    # An ungated recipe is unlocked for every vault without a lookup.
    assert await recipe_unlock_service.is_unlocked(
        async_session,
        vault_id=vault.id,
        item_type="weapon",
        entry=catalog_entry("weapon", COMMON_WEAPON),
    )


@pytest.mark.asyncio
async def test_scrapping_ungated_items_does_nothing(async_session: AsyncSession, vault: Vault) -> None:
    assert (
        await recipe_unlock_service.record_scrap(
            async_session, vault_id=vault.id, item_type="weapon", item_name=COMMON_WEAPON
        )
        is None
    )


@pytest.mark.asyncio
async def test_a_second_scrap_does_not_re_unlock(async_session: AsyncSession, vault: Vault) -> None:
    await recipe_unlock_service.record_scrap(
        async_session, vault_id=vault.id, item_type="weapon", item_name=RARE_WEAPON
    )
    await async_session.commit()

    again = await recipe_unlock_service.record_scrap(
        async_session, vault_id=vault.id, item_type="weapon", item_name=RARE_WEAPON
    )
    assert again is None


@pytest.mark.asyncio
async def test_list_recipes_lists_locked_schematics_with_hint(async_session: AsyncSession, vault: Vault) -> None:
    recipes = {recipe.name: recipe for recipe in await crafting_service.list_recipes(async_session, vault.id, "weapon")}

    assert COMMON_WEAPON in recipes
    common = recipes[COMMON_WEAPON]
    assert common.unlocked is True
    assert common.unlock_hint is None

    assert LEGENDARY_WEAPON in recipes
    legendary = recipes[LEGENDARY_WEAPON]
    assert legendary.unlocked is False
    assert legendary.unlock_hint is not None
    assert "reverse-engineer" in legendary.unlock_hint

    assert RARE_WEAPON in recipes
    rare = recipes[RARE_WEAPON]
    assert rare.unlocked is False
    assert rare.unlock_hint == "Scrap a Baseball bat to reverse-engineer this schematic"


@pytest.mark.asyncio
async def test_list_recipes_shows_a_legendary_once_learned(async_session: AsyncSession, vault: Vault) -> None:
    await recipe_unlock_service.record_scrap(
        async_session, vault_id=vault.id, item_type="weapon", item_name=LEGENDARY_WEAPON
    )
    await async_session.commit()

    recipes = {recipe.name: recipe for recipe in await crafting_service.list_recipes(async_session, vault.id, "weapon")}

    learned = recipes[LEGENDARY_WEAPON]
    assert learned.unlocked is True
    assert learned.unlock_hint is None


@pytest.mark.asyncio
async def test_list_recipes_separates_having_junk_from_being_affordable(
    async_session: AsyncSession, vault: Vault
) -> None:
    storage = await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await _add_junk(async_session, storage, RarityEnum.COMMON, 10)
    await _add_junk(async_session, storage, RarityEnum.RARE, 10)
    vault.bottle_caps = 0
    await async_session.commit()

    recipes = {r.name: r for r in await crafting_service.list_recipes(async_session, vault.id, "weapon")}
    rare = recipes[RARE_WEAPON]

    # Enough junk to craft, but no caps: the "Craftable now" filter keeps it while
    # the Start button stays disabled.
    assert rare.has_junk is True
    assert rare.can_craft is False


@pytest.mark.asyncio
async def test_start_order_refuses_a_locked_recipe(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")

    with pytest.raises(ValidationException, match="reverse-engineer"):
        await crafting_service.start_order(async_session, vault.id, LEGENDARY_WEAPON, "weapon")


@pytest.mark.asyncio
async def test_start_order_allows_an_unlocked_recipe(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")
    await recipe_unlock_service.record_scrap(
        async_session, vault_id=vault.id, item_type="weapon", item_name=LEGENDARY_WEAPON
    )
    await async_session.commit()

    # The lock gate no longer fires; the order fails only on materials, which is not
    # a lock error.
    with pytest.raises(InsufficientResourcesException):
        await crafting_service.start_order(async_session, vault.id, LEGENDARY_WEAPON, "weapon")
