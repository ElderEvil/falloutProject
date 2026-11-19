"""Schemas for workshop crafting — recipes, orders, and collection."""

from typing import Literal
from uuid import UUID

from pydantic import Field
from sqlmodel import SQLModel

from app.core.enums import CraftingOrderStatus, RarityEnum
from app.utils.serialize_types import OptionalUTCDateTimeJSON, UTCDateTimeJSON

CraftableItemType = Literal["weapon", "outfit", "theme"]


class CraftingRecipeRead(SQLModel):
    """Catalog entry with costs, affordability, and unlock state; unlearned gated
    schematics stay listed (unlocked/unlock_hint tell the UI to disable + explain).
    """

    name: str
    item_type: CraftableItemType
    rarity: RarityEnum
    value: int | None = None
    stat: str
    junk_types: list[str] = []
    junk_materials: dict[str, int] = {}
    available_junk: dict[str, int] = {}
    ability_sum: int = 0
    duration_seconds: int = 0
    junk_cost: int
    caps_cost: int
    can_craft: bool
    missing_junk: int = 0
    has_junk: bool = False
    unlocked: bool = True
    unlock_hint: str | None = None
    style: str | None = None
    owned: bool = False


class CraftRequest(SQLModel):
    """Craft one catalog item at its matching workshop."""

    item_name: str = Field(min_length=1, max_length=64)
    item_type: CraftableItemType


class CraftResultRead(SQLModel):
    """Crafted item plus spent materials; item_id is null for theme orders (they
    grant permanent ownership, not a storage item).
    """

    item_type: str
    item_id: UUID | None = None
    name: str
    rarity: RarityEnum
    junk_spent: int
    caps_spent: int


class CraftingRecipesRead(SQLModel):
    """Recipe list for a vault's workshops."""

    recipes: list[CraftingRecipeRead] = []


class CraftingOrderCreate(SQLModel):
    """Internal create shape for a queued workshop order."""

    vault_id: UUID
    room_id: UUID
    item_name: str = Field(min_length=3, max_length=64)
    item_type: str = Field(max_length=16)
    rarity: RarityEnum
    started_at: UTCDateTimeJSON
    estimated_completion_at: UTCDateTimeJSON
    junk_spent: int = Field(default=0, ge=0)
    caps_spent: int = Field(default=0, ge=0)
    required_stat: str = Field(max_length=16)
    ability_sum_at_start: int = Field(default=0, ge=0)


class CraftingOrderUpdate(SQLModel):
    """Mutable order fields (the queue only advances status and progress)."""

    status: CraftingOrderStatus | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    completed_at: OptionalUTCDateTimeJSON = None


class CraftingOrderRead(SQLModel):
    """One queued or finished workshop order."""

    id: UUID
    room_id: UUID
    item_name: str
    item_type: str
    rarity: RarityEnum
    status: CraftingOrderStatus
    progress: float
    started_at: UTCDateTimeJSON
    estimated_completion_at: UTCDateTimeJSON
    completed_at: OptionalUTCDateTimeJSON = None
    cancelled_at: OptionalUTCDateTimeJSON = None
    junk_spent: int
    caps_spent: int
    required_stat: str
    ability_sum_at_start: int


class CraftingOrdersRead(SQLModel):
    orders: list[CraftingOrderRead] = []
