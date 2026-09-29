"""Tests for learning gated crafting recipes by scrapping the exact item (v1)."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.vault import Vault
from app.services.crafting_service import crafting_service
from app.services.recipe_unlock_service import (
    catalog_entry,
    recipe_unlock_service,
    scrap_unlock_count,
    unlock_hint,
)
from app.tests.test_services.test_crafting_service import _add_workshop, _make_storage
from app.utils.exceptions import InsufficientResourcesException, ValidationException

LEGENDARY_WEAPON = "Power fist"
COMMON_WEAPON = "Pipe pistol"


def test_only_legendary_recipes_are_gated_by_default():
    legendary = catalog_entry("weapon", LEGENDARY_WEAPON)
    assert legendary is not None
    assert scrap_unlock_count(legendary) == game_config.crafting.scrap_unlock_count("legendary") == 1
    assert unlock_hint("weapon", LEGENDARY_WEAPON) == "Scrap 1 Weapon to learn this recipe"

    assert scrap_unlock_count(catalog_entry("weapon", COMMON_WEAPON)) == 0
    assert unlock_hint("weapon", COMMON_WEAPON) is None


def test_catalog_override_beats_the_rarity_default():
    entry = {"rarity": "common", "craft": {"unlock": {"scrap": {"count": 5}}}}
    assert scrap_unlock_count(entry) == 5
    assert unlock_hint("weapon", "not in the catalog") is None


def test_catalog_entry_matching_ignores_case_and_whitespace():
    assert catalog_entry("weapon", f"  {LEGENDARY_WEAPON.upper()}  ") is not None
    assert catalog_entry("outfit", LEGENDARY_WEAPON) is None


@pytest.mark.asyncio
async def test_scrapping_a_gated_item_unlocks_its_recipe(async_session: AsyncSession, vault: Vault) -> None:
    assert not await recipe_unlock_service.is_unlocked(
        async_session, vault_id=vault.id, item_type="weapon", recipe_name=LEGENDARY_WEAPON
    )

    unlocked = await recipe_unlock_service.record_scrap(
        async_session, vault_id=vault.id, item_type="weapon", item_name=LEGENDARY_WEAPON
    )
    await async_session.commit()

    assert unlocked == {"item_type": "weapon", "recipe_name": LEGENDARY_WEAPON}
    assert await recipe_unlock_service.is_unlocked(
        async_session, vault_id=vault.id, item_type="weapon", recipe_name=LEGENDARY_WEAPON
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
        async_session, vault_id=vault.id, item_type="weapon", item_name=LEGENDARY_WEAPON
    )
    await async_session.commit()

    again = await recipe_unlock_service.record_scrap(
        async_session, vault_id=vault.id, item_type="weapon", item_name=LEGENDARY_WEAPON
    )
    assert again is None


@pytest.mark.asyncio
async def test_list_recipes_flags_locked_legendaries(async_session: AsyncSession, vault: Vault) -> None:
    recipes = await crafting_service.list_recipes(async_session, vault.id, "weapon")

    power_fist = next(recipe for recipe in recipes if recipe.name == LEGENDARY_WEAPON)
    assert power_fist.unlocked is False
    assert power_fist.unlock_hint == "Scrap 1 Weapon to learn this recipe"

    pipe_pistol = next(recipe for recipe in recipes if recipe.name == COMMON_WEAPON)
    assert pipe_pistol.unlocked is True
    assert pipe_pistol.unlock_hint is None


@pytest.mark.asyncio
async def test_start_order_refuses_a_locked_recipe(async_session: AsyncSession, vault: Vault) -> None:
    await _make_storage(async_session, vault)
    await _add_workshop(async_session, vault, "Weapon workshop")

    with pytest.raises(ValidationException, match="locked"):
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
