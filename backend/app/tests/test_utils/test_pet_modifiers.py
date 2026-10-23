"""Pet effect catalog and resolver tests (Phase B1).

The resolver is pure and session-free: no DB, no lazy IO. Catalog keys are the
same ``.strip().casefold()`` names as ``PET_NAME_TO_IMAGE_FILE`` so art and
effects stay aligned — pinned by the naming-source consistency test.
"""

from types import SimpleNamespace

import pytest

from app.models.pet import Pet
from app.options.pet_modifiers import (
    NEUTRAL_EFFECT,
    PET_DESCRIPTION_BY_NAME,
    PET_EFFECT_BY_NAME,
    PetEffect,
    pet_description_for_name,
    pet_effect_for_name,
    pet_modifiers_for,
)
from app.utils.equipped import equipped_pet
from app.utils.pet_assets import PET_NAME_TO_IMAGE_FILE, get_pet_image_url


def _pet(name: str) -> Pet:
    return Pet(name=name, rarity="Legendary")


def test_known_pet_name_resolves_to_its_effect() -> None:
    effect = pet_effect_for_name("CX404")
    assert effect is PET_EFFECT_BY_NAME["cx404"]
    assert effect.luck == 2
    assert effect.caps_pct == pytest.approx(0.25)


def test_pet_effect_for_name_normalizes_whitespace_and_case() -> None:
    assert pet_effect_for_name("  CX404  ") is PET_EFFECT_BY_NAME["cx404"]
    assert pet_effect_for_name("Vault-Tec Parrot") is PET_EFFECT_BY_NAME["vault-tec parrot"]


def test_unknown_blank_or_none_name_is_neutral() -> None:
    assert pet_effect_for_name("Deathclaw") is NEUTRAL_EFFECT
    assert pet_effect_for_name("  ") is NEUTRAL_EFFECT
    assert pet_effect_for_name(None) is NEUTRAL_EFFECT


def test_equipped_pet_reads_dict_and_returns_none_when_absent() -> None:
    assert equipped_pet(SimpleNamespace()) is None
    pet = _pet("CX404")
    assert equipped_pet(SimpleNamespace(pet=pet)) is pet


def test_pet_modifiers_for_returns_neutral_without_pet() -> None:
    assert pet_modifiers_for(SimpleNamespace()) is NEUTRAL_EFFECT


def test_pet_modifiers_for_resolves_equipped_pet_by_name() -> None:
    entity = SimpleNamespace(pet=_pet("CX404"))
    assert pet_modifiers_for(entity) is PET_EFFECT_BY_NAME["cx404"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # Values are external balance data from the Fallout wiki Manx/Dalmatian pet tables.
        ("Genius", 0.25),
        ("Stubbs", 0.50),
        ("Shakespeare", 0.75),
        ("Lucky", 0.50),
        ("Pongo", 0.75),
        ("CX404", 0.0),
    ],
)
def test_twins_chance_pets_resolve_to_their_canonical_bonus(name: str, expected: float) -> None:
    """The canonical Twins-chance pets carry their Fallout Shelter bonus; others stay neutral."""
    assert pet_effect_for_name(name).twin_chance_pct == pytest.approx(expected)


def test_catalog_covers_every_effect_field_at_least_once() -> None:
    uncovered = [
        field
        for field in PetEffect.__dataclass_fields__
        if all(getattr(effect, field) == 0 for effect in PET_EFFECT_BY_NAME.values())
    ]
    assert uncovered == []


def test_every_catalog_key_resolves_to_real_pet_art() -> None:
    unresolved = [name for name in PET_EFFECT_BY_NAME if get_pet_image_url(name) is None]
    assert unresolved == []


def test_known_pet_name_resolves_to_its_description() -> None:
    assert pet_description_for_name("CX404") == PET_DESCRIPTION_BY_NAME["cx404"]


def test_pet_description_for_name_normalizes_whitespace_and_case() -> None:
    assert pet_description_for_name("  Vault-Tec Parrot  ") == PET_DESCRIPTION_BY_NAME["vault-tec parrot"]


def test_unknown_blank_or_none_name_has_no_description() -> None:
    assert pet_description_for_name("Deathclaw") is None
    assert pet_description_for_name("  ") is None
    assert pet_description_for_name(None) is None


def test_every_catalogued_pet_has_a_description() -> None:
    assert [name for name in PET_EFFECT_BY_NAME if name not in PET_DESCRIPTION_BY_NAME] == []


def test_every_art_mapped_pet_has_a_description() -> None:
    assert [name for name in PET_NAME_TO_IMAGE_FILE if name not in PET_DESCRIPTION_BY_NAME] == []


def test_description_catalog_has_no_extra_keys() -> None:
    assert [name for name in PET_DESCRIPTION_BY_NAME if name not in PET_NAME_TO_IMAGE_FILE] == []


def test_descriptions_are_non_blank_and_reasonably_short() -> None:
    assert [name for name, text in PET_DESCRIPTION_BY_NAME.items() if not text.strip()] == []
    assert [name for name, text in PET_DESCRIPTION_BY_NAME.items() if len(text) > 120] == []


def test_pet_read_exposes_the_catalog_description() -> None:
    from datetime import datetime
    from uuid import uuid4

    from app.core.enums import RarityEnum
    from app.schemas.pet import PetRead

    now = datetime.now()
    read = PetRead(id=uuid4(), created_at=now, updated_at=now, name="CX404", rarity=RarityEnum.LEGENDARY, value=100)

    assert read.description == PET_DESCRIPTION_BY_NAME["cx404"]
    unknown = PetRead(id=uuid4(), created_at=now, updated_at=now, name="Deathclaw", rarity=RarityEnum.COMMON, value=10)
    assert unknown.description is None
