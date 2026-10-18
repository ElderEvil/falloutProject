"""How a held loot entry resolves against the shipped catalog.

Exploration and incidents hold loot under the same shape but name the catalog
field differently (``item_name`` vs ``name``) and describe their junk
differently. One lookup answers both "what row does this build into" and "what
is this worth", so a name that can be taken can always be sold for the same
price.
"""

from uuid import uuid4

import pytest

from app.core.enums import RarityEnum
from app.core.game_config import game_config
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.services.loot_overflow_service import loot_overflow_service
from app.utils.static_data import game_data_store


@pytest.mark.parametrize("name_key", ["item_name", "name"])
def test_catalog_weapon_resolves_whatever_the_owner_calls_its_name_field(name_key):
    """Exploration writes ``item_name``, incidents ``name``; both must resolve by name."""
    catalog = game_data_store.weapons[0]
    loot = {name_key: catalog.name.upper(), "item_type": "weapon", "rarity": "Legendary", "quantity": 1}

    row = loot_overflow_service.build_storage_row(loot, uuid4(), junk_description="irrelevant")

    assert isinstance(row, Weapon)
    assert row.name == catalog.name
    assert row.rarity == RarityEnum.LEGENDARY
    assert row.value == catalog.value


def test_catalog_outfit_resolves_case_insensitively():
    catalog = game_data_store.outfits[0]
    loot = {"item_name": catalog.name.lower(), "item_type": "outfit", "rarity": "common", "quantity": 1}

    row = loot_overflow_service.build_storage_row(loot, uuid4(), junk_description="irrelevant")

    assert isinstance(row, Outfit)
    assert row.name == catalog.name
    assert row.rarity == RarityEnum.COMMON


@pytest.mark.parametrize("description", ["Found during wasteland exploration", "Recovered from an incident"])
def test_junk_is_priced_by_rarity_and_described_by_its_owner(description: str):
    loot = {"item_name": "Desk Fan", "item_type": "junk", "rarity": "common", "quantity": 1}

    row = loot_overflow_service.build_storage_row(loot, uuid4(), junk_description=description)

    assert isinstance(row, Junk)
    assert row.value == game_config.exploration.junk_value_common
    assert row.description == description


def test_missing_item_type_defaults_to_junk():
    row = loot_overflow_service.build_storage_row(
        {"item_name": "Desk Fan", "rarity": "common"}, uuid4(), junk_description="anything"
    )

    assert isinstance(row, Junk)


def test_unknown_rarity_falls_back_to_common():
    loot = {"item_name": "Desk Fan", "item_type": "junk", "rarity": "mythic", "quantity": 1}

    row = loot_overflow_service.build_storage_row(loot, uuid4(), junk_description="anything")

    assert isinstance(row, Junk)
    assert row.rarity == RarityEnum.COMMON


@pytest.mark.parametrize("item_type", ["weapon", "outfit"])
def test_unknown_catalog_row_returns_none_rather_than_a_defaulted_item(item_type: str):
    loot = {"item_name": "Nonexistent Relic", "item_type": item_type, "rarity": "common", "quantity": 1}

    assert loot_overflow_service.build_storage_row(loot, uuid4(), junk_description="anything") is None


@pytest.mark.parametrize("item_type", ["weapon", "outfit"])
def test_pricing_resolves_a_catalog_name_case_insensitively(item_type: str):
    """An entry the build path accepts must price the same, or take succeeds and sell fails."""
    catalog = game_data_store.weapons[0] if item_type == "weapon" else game_data_store.outfits[0]
    loot = {"item_name": catalog.name.upper(), "item_type": item_type, "rarity": "common", "quantity": 1}

    assert loot_overflow_service.unit_value_of(loot) == (catalog.value or 0)


@pytest.mark.parametrize("item_type", ["weapon", "outfit"])
def test_an_entry_that_can_be_taken_can_always_be_sold(item_type: str):
    """Regression: an upper-cased catalog name built fine but raised when priced."""
    catalog = game_data_store.weapons[0] if item_type == "weapon" else game_data_store.outfits[0]
    loot = {"item_name": catalog.name.upper(), "item_type": item_type, "rarity": "common", "quantity": 2}

    assert loot_overflow_service.build_storage_row(loot, uuid4(), junk_description="anything") is not None
    assert loot_overflow_service.value_of(loot) == (catalog.value or 0) * 2
