from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.enums import RarityEnum
from app.models.pet import Pet
from app.options.pet_modifiers import (
    MAX_DAMAGE_PCT_BONUS,
    MAX_PCT_BONUS,
    NEUTRAL_EFFECT,
    PET_DESCRIPTION_BY_NAME,
    PET_EFFECT_BY_NAME,
    PetEffect,
    pet_description_for_name,
    pet_effect_for_name,
    pet_modifiers_for,
)
from app.schemas.pet import PetRead
from app.utils.equipped import equipped_pet
from app.utils.pet_assets import PET_NAME_TO_IMAGE_FILE, get_pet_image_url

FALLBACK_NAMES = ("Deathclaw", "  ", None)


def _pet(name: str) -> Pet:
    return Pet(name=name, rarity="Legendary")


def test_pet_effect_lookup_and_normalization() -> None:
    effect = pet_effect_for_name("CX404")
    assert effect is PET_EFFECT_BY_NAME["cx404"]
    assert effect.luck == 2
    assert effect.caps_pct == pytest.approx(0.25)
    assert pet_effect_for_name("  CX404  ") is PET_EFFECT_BY_NAME["cx404"]
    assert pet_effect_for_name("Vault-Tec Parrot") is PET_EFFECT_BY_NAME["vault-tec parrot"]
    for name in FALLBACK_NAMES:
        assert pet_effect_for_name(name) is NEUTRAL_EFFECT


def test_equipped_and_modifier_resolution() -> None:
    assert equipped_pet(SimpleNamespace()) is None
    pet = _pet("CX404")
    assert equipped_pet(SimpleNamespace(pet=pet)) is pet
    assert pet_modifiers_for(SimpleNamespace()) is NEUTRAL_EFFECT
    assert pet_modifiers_for(SimpleNamespace(pet=pet)) is PET_EFFECT_BY_NAME["cx404"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # External balance data from the Fallout wiki Manx/Dalmatian pet tables.
        ("Genius", 0.25),
        ("Stubbs", 0.50),
        ("Shakespeare", 0.75),
        ("Lucky", 0.50),
        ("Pongo", 0.75),
        ("CX404", 0.0),
    ],
)
def test_twins_chance_pets_resolve_to_their_canonical_bonus(name: str, expected: float) -> None:
    assert pet_effect_for_name(name).twin_chance_pct == pytest.approx(expected)


@pytest.mark.parametrize(
    ("name", "damage_pct", "incident_response_pct", "max_health"),
    [("Baby Deathclaw", 0.35, 0.25, 0), ("Yao Guai Cub", 0.25, 0.0, 25)],
)
def test_exotic_pet_effects_are_catalogued_and_within_caps(
    name: str, damage_pct: float, incident_response_pct: float, max_health: int
) -> None:
    effect = pet_effect_for_name(name)
    assert effect.damage_pct == pytest.approx(damage_pct)
    assert effect.incident_response_pct == pytest.approx(incident_response_pct)
    assert effect.max_health == max_health
    assert effect.damage_pct <= MAX_DAMAGE_PCT_BONUS
    assert effect.incident_response_pct <= MAX_PCT_BONUS
    assert pet_description_for_name(name)
    assert get_pet_image_url(name)


def test_catalog_self_consistency() -> None:
    assert [
        field
        for field in PetEffect.model_fields
        if all(getattr(effect, field) == 0 for effect in PET_EFFECT_BY_NAME.values())
    ] == []
    assert [name for name in PET_EFFECT_BY_NAME if get_pet_image_url(name) is None] == []
    assert [name for name in PET_EFFECT_BY_NAME if name not in PET_DESCRIPTION_BY_NAME] == []
    assert [name for name in PET_NAME_TO_IMAGE_FILE if name not in PET_DESCRIPTION_BY_NAME] == []
    assert [name for name in PET_DESCRIPTION_BY_NAME if name not in PET_NAME_TO_IMAGE_FILE] == []
    assert [name for name, text in PET_DESCRIPTION_BY_NAME.items() if not text.strip()] == []
    assert [name for name, text in PET_DESCRIPTION_BY_NAME.items() if len(text) > 120] == []
    assert pet_description_for_name("CX404") == PET_DESCRIPTION_BY_NAME["cx404"]
    assert pet_description_for_name("  Vault-Tec Parrot  ") == PET_DESCRIPTION_BY_NAME["vault-tec parrot"]
    for name in FALLBACK_NAMES:
        assert pet_description_for_name(name) is None
    now = datetime.now()
    read = PetRead(id=uuid4(), created_at=now, updated_at=now, name="CX404", rarity=RarityEnum.LEGENDARY, value=100)
    assert read.description == PET_DESCRIPTION_BY_NAME["cx404"]
    unknown = PetRead(id=uuid4(), created_at=now, updated_at=now, name="Deathclaw", rarity=RarityEnum.COMMON, value=10)
    assert unknown.description is None
