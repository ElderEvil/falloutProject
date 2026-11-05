"""Default item prices and caller overrides at the schema boundary."""

import pytest

from app.core.enums import RarityEnum
from app.schemas.item import ItemCreate
from app.schemas.junk import JunkCreate, JunkUpdate


@pytest.mark.parametrize(("rarity", "expected"), [("common", 10), ("rare", 100), ("legendary", 500)])
@pytest.mark.parametrize("as_enum", [False, True])
@pytest.mark.parametrize("value_fields", [{}, {"value": None}])
def test_junk_defaults_preserve_existing_prices(rarity, expected, as_enum, value_fields):
    junk = JunkCreate.model_validate(
        {
            "name": "Desk Fan",
            "rarity": RarityEnum(rarity) if as_enum else rarity,
            "junk_type": "valuables",
            "description": "A dusty desk fan",
            **value_fields,
        }
    )
    assert junk.value == expected


@pytest.mark.parametrize("value", [0, 42])
def test_junk_preserves_explicit_prices(value):
    junk = JunkCreate.model_validate(
        {
            "name": "Desk Fan",
            "rarity": "rare",
            "junk_type": "valuables",
            "description": "A dusty desk fan",
            "value": value,
        }
    )
    assert junk.value == value


def test_junk_update_keeps_partial_value_semantics():
    assert JunkUpdate.model_validate({"rarity": "rare"}).value == 100
    assert JunkUpdate.model_validate({"value": None}).value is None


@pytest.mark.parametrize(("rarity", "expected"), [("common", 10), ("rare", 100), ("legendary", 500)])
def test_generic_item_can_resolve_its_default_price(rarity, expected):
    item = ItemCreate.model_validate({"name": "Supply crate", "rarity": rarity})
    assert item.value == expected
