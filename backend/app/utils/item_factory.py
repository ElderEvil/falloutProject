"""Shared constructors for catalog-backed weapons, outfits, and junk.

Both reward settlement and crafting build items from the same JSON catalogs
(`items/weapons.json`, `items/outfits/*.json`), so the mapping from catalog
shape to ORM model lives here exactly once. Junk rows carry no catalog row:
pricing and prose stay caller-owned because incidents and exploration value
and describe held junk differently.
"""

from typing import Any

from pydantic import UUID4

from app.core.enums import GenderEnum, JunkTypeEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.utils.outfit_assets import get_outfit_image_url
from app.utils.weapon_assets import get_weapon_image_url


def build_weapon(data: dict[str, Any], rarity: RarityEnum | str, storage_id: UUID4 | None = None) -> Weapon:
    """Build a Weapon from a catalog dict, tolerating omitted stat fields."""
    name = str(data["name"])
    return Weapon(
        name=name,
        rarity=rarity,
        weapon_type=WeaponTypeEnum(str(data.get("weapon_type", "melee")).lower()),
        weapon_subtype=WeaponSubtypeEnum(str(data.get("weapon_subtype", "blunt")).lower()),
        stat=str(data.get("stat", "strength")),
        damage_min=int(data.get("damage_min", 1)),
        damage_max=int(data.get("damage_max", 3)),
        value=data.get("value"),
        image_url=get_weapon_image_url(name),
        storage_id=storage_id,
    )


def build_outfit(data: dict[str, Any], rarity: RarityEnum | str, storage_id: UUID4 | None = None) -> Outfit:
    """Build an Outfit from a catalog dict; SPECIAL bonuses stay name-derived."""
    name = str(data["name"])
    gender = data.get("gender")
    declared_radiation_resist = data.get("radiation_resist")
    return Outfit(
        name=name,
        rarity=rarity,
        outfit_type=OutfitTypeEnum(str(data.get("outfit_type", OutfitTypeEnum.COMMON)).lower()),
        gender=GenderEnum(str(gender).lower()) if gender else None,
        fire_resist=float(data.get("fire_resist") or 0.0),
        radiation_resist=float(declared_radiation_resist) if declared_radiation_resist is not None else None,
        value=data.get("value"),
        image_url=get_outfit_image_url(name),
        storage_id=storage_id,
    )


def build_junk(
    name: str,
    rarity: RarityEnum | str,
    storage_id: UUID4 | None = None,
    *,
    value: int,
    description: str,
) -> Junk:
    """Build a Junk row; value and description stay caller-owned."""
    return Junk(
        name=name,
        junk_type=JunkTypeEnum.VALUABLES,
        rarity=rarity,
        value=value,
        description=description,
        storage_id=storage_id,
    )
