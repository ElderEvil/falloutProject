"""Tests for the arena actor reference resolver (issue #818)."""

from app.core.enums import (
    AgeGroupEnum,
    AssetRole,
    GenderEnum,
    OutfitTypeEnum,
    RarityEnum,
    WeaponSubtypeEnum,
    WeaponTypeEnum,
)
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.utils.actor_assets import get_actor_assets
from app.utils.asset_manifest import load_asset_records


def _record(role: AssetRole, catalog_key: str):
    return next(r for r in load_asset_records() if r.role == role and r.catalog_key == catalog_key)


def _make_dweller(*, age_group: AgeGroupEnum = AgeGroupEnum.ADULT, is_adult: bool = True) -> Dweller:
    return Dweller(
        first_name="Test",
        last_name="Dweller",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        age_group=age_group,
        is_adult=is_adult,
    )


def _make_outfit() -> Outfit:
    return Outfit(name="Overcoat", rarity=RarityEnum.COMMON, outfit_type=OutfitTypeEnum.COMMON)


def _make_weapon() -> Weapon:
    return Weapon(
        name="Rifle",
        rarity=RarityEnum.COMMON,
        weapon_type=WeaponTypeEnum.GUN,
        weapon_subtype=WeaponSubtypeEnum.RIFLE,
        stat="P",
        damage_min=1,
        damage_max=5,
    )


def test_adult_without_equipment_gets_body_layer_only() -> None:
    base = _record(AssetRole.ARENA_ACTOR, "adult.vault_suit")

    assets = get_actor_assets(_make_dweller(), outfit_name=None, weapon_name=None)

    assert assets is not None
    assert assets.base_key == "adult.vault_suit"
    assert assets.variant_key is None
    assert assets.canvas_width == base.actor.canvas_width
    assert assets.canvas_height == base.actor.canvas_height
    assert assets.baseline_y == base.actor.baseline_y
    assert [(layer.slot, layer.z) for layer in assets.layers] == [("body", 10)]
    assert assets.layers[0].path == base.path

    actor = assets.to_arena_actor()
    assert actor.base_key == "adult.vault_suit"
    assert actor.variant_url is None
    assert [layer.slot for layer in actor.layers] == ["body"]
    assert actor.layers[0].url == base.path


def test_adult_with_outfit_appends_outfit_layer() -> None:
    outfit = _record(AssetRole.ARENA_EQUIPMENT, "overcoat")

    assets = get_actor_assets(_make_dweller(), outfit_name="Tattered longcoat", weapon_name=None)

    assert assets is not None
    assert [(layer.slot, layer.z) for layer in assets.layers] == [("body", 10), ("outfit", 20)]
    assert assets.layers[1].path == outfit.path


def test_adult_with_weapon_appends_weapon_layer() -> None:
    weapon = _record(AssetRole.ARENA_EQUIPMENT, "rifle")

    assets = get_actor_assets(_make_dweller(), outfit_name=None, weapon_name="Assault rifle")

    assert assets is not None
    assert [(layer.slot, layer.z) for layer in assets.layers] == [("body", 10), ("weapon", 30)]
    assert assets.layers[1].path == weapon.path


def test_adult_with_both_appends_outfit_then_weapon() -> None:
    assets = get_actor_assets(_make_dweller(), outfit_name="Tattered longcoat", weapon_name="Assault rifle")

    assert assets is not None
    assert [layer.slot for layer in assets.layers] == ["body", "outfit", "weapon"]


def test_non_adult_resolves_none() -> None:
    for age_group in (AgeGroupEnum.CHILD, AgeGroupEnum.TEEN):
        assert get_actor_assets(_make_dweller(age_group=age_group), outfit_name=None, weapon_name=None) is None
        assert get_actor_assets(_make_dweller(age_group=age_group), outfit_name="Overcoat", weapon_name="Rifle") is None


def test_adult_flag_false_resolves_none() -> None:
    assert get_actor_assets(_make_dweller(is_adult=False), outfit_name=None, weapon_name=None) is None


def test_unsupported_equipment_adds_no_layer() -> None:
    """Items without actor art fall back to the base actor, never mismatched art."""
    assets = get_actor_assets(_make_dweller(), outfit_name="Lab coat", weapon_name="Pipe rifle")

    assert assets is not None
    assert [layer.slot for layer in assets.layers] == ["body"]


def test_supported_equipment_matching_is_case_insensitive() -> None:
    assets = get_actor_assets(_make_dweller(), outfit_name="  tattered longcoat ", weapon_name="ASSAULT RIFLE")

    assert assets is not None
    assert [layer.slot for layer in assets.layers] == ["body", "outfit", "weapon"]
