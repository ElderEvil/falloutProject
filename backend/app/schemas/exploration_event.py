"""Schemas for exploration events and related data structures."""

from typing import Literal

from pydantic import BaseModel, Field


class ItemSchema(BaseModel):
    """Base schema for an item found during exploration."""

    name: str = Field(..., description="Item name")
    rarity: str = Field(..., description="Item rarity (Common, Rare, Legendary)")
    value: int = Field(..., description="Item value in caps")


class WeaponSchema(ItemSchema):
    """Schema for weapon items."""

    weapon_type: str = Field(..., description="Weapon type (Melee, Ranged, Energy)")
    weapon_subtype: str = Field(..., description="Weapon subtype (Blunt, Sharp, Pistol, etc.)")
    stat: str = Field(..., description="Primary stat (strength, perception, agility)")
    damage_min: int = Field(..., ge=0, description="Minimum damage")
    damage_max: int = Field(..., ge=0, description="Maximum damage")


class OutfitSchema(ItemSchema):
    """Schema for outfit items."""

    outfit_type: str = Field(..., description="Outfit type (Common Outfit, Rare Outfit, Legendary Outfit)")


class JunkSchema(ItemSchema):
    """Schema for junk items - only needs base ItemSchema fields."""


# Union type for any loot item
LootItemSchema = WeaponSchema | OutfitSchema | JunkSchema


class LootSchema(BaseModel):
    """Schema for loot found during exploration."""

    item: ItemSchema = Field(..., description="Item details")
    item_type: str = Field(..., description="Item type (weapon, outfit, junk)")
    caps: int = Field(..., description="Caps found with the item")


class EnemySchema(BaseModel):
    """Schema for enemy data."""

    name: str = Field(..., description="Enemy name")
    difficulty: int = Field(..., ge=1, le=5, description="Enemy difficulty level (1-5)")
    min_damage: int = Field(..., ge=0, description="Minimum damage dealt")
    max_damage: int = Field(..., ge=0, description="Maximum damage dealt")


class CombatEventSchema(BaseModel):
    """Schema for combat event data."""

    type: Literal["combat"] = Field(default="combat", description="Event type")
    description: str = Field(..., description="Event description")
    health_loss: int = Field(..., ge=0, description="Health lost in combat")
    enemy: str = Field(..., description="Enemy name")
    victory: bool = Field(..., description="Whether dweller won the combat")


class LootEventSchema(BaseModel):
    """Schema for loot event data."""

    type: Literal["loot"] = Field(default="loot", description="Event type")
    description: str = Field(..., description="Event description")
    loot: LootSchema = Field(..., description="Loot found")


class DangerEventSchema(BaseModel):
    """Schema for danger event data."""

    type: Literal["danger"] = Field(default="danger", description="Event type")
    description: str = Field(..., description="Event description")
    health_loss: int = Field(..., ge=0, description="Health lost from danger")


class RestEventSchema(BaseModel):
    """Schema for rest event data."""

    type: Literal["rest"] = Field(default="rest", description="Event type")
    description: str = Field(..., description="Event description")
    health_restored: int = Field(..., ge=0, description="Health restored from rest")


class CombatOutcomeSchema(BaseModel):
    """Schema for combat outcome calculation results."""

    victory: bool = Field(..., description="Whether dweller won the combat")
    health_loss: int = Field(..., ge=0, description="Health lost in combat")
    description: str = Field(..., description="Combat outcome description")


class RewardsSchema(BaseModel):
    """Schema for exploration completion rewards."""

    caps: int = Field(..., ge=0, description="Total caps earned")
    items: list[dict] = Field(default_factory=list, description="Items collected and transferred to storage")
    overflow_items: list[dict] = Field(default_factory=list, description="Items dropped due to storage being full")
    experience: int = Field(..., ge=0, description="Experience earned")
    distance: int = Field(..., ge=0, description="Distance traveled")
    enemies_defeated: int = Field(..., ge=0, description="Number of enemies defeated")
    events_encountered: int = Field(..., ge=0, description="Number of events encountered")
    progress_percentage: int | None = Field(None, ge=0, le=100, description="Progress percentage (for recalls)")
    recalled_early: bool | None = Field(None, description="Whether exploration was recalled early")


# Union type for all event types
ExplorationEvent = CombatEventSchema | LootEventSchema | DangerEventSchema | RestEventSchema
