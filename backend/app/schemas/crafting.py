"""Schemas for workshop crafting — recipes, orders, and collection."""

from datetime import datetime
from typing import Literal

from pydantic import UUID4, Field
from sqlmodel import SQLModel

from app.core.enums import RarityEnum
from app.models.crafting_order import CraftingOrderStatus

CraftableItemType = Literal["weapon", "outfit"]


class CraftingRecipeRead(SQLModel):
    """One catalog entry with its costs, affordability, and unlock state.

    A gated schematic the vault has not learned is still listed so the player can
    see what is out there; ``unlocked``/``unlock_hint`` tell the UI to disable it
    and explain how to learn it.
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


class CraftRequest(SQLModel):
    """Craft one catalog item at its matching workshop."""

    item_name: str = Field(min_length=1, max_length=64)
    item_type: CraftableItemType


class CraftResultRead(SQLModel):
    """The crafted item plus the materials that were spent."""

    item_type: str
    item_id: UUID4
    name: str
    rarity: RarityEnum
    junk_spent: int
    caps_spent: int


class CraftingRecipesRead(SQLModel):
    """Recipe list for a vault's workshops."""

    recipes: list[CraftingRecipeRead] = []


class CraftingOrderCreate(SQLModel):
    """Internal create shape for a queued workshop order."""

    vault_id: UUID4
    room_id: UUID4
    item_name: str = Field(min_length=3, max_length=64)
    item_type: str = Field(max_length=16)
    rarity: RarityEnum
    started_at: datetime
    estimated_completion_at: datetime
    junk_spent: int = Field(default=0, ge=0)
    caps_spent: int = Field(default=0, ge=0)
    required_stat: str = Field(max_length=16)
    ability_sum_at_start: int = Field(default=0, ge=0)


class CraftingOrderUpdate(SQLModel):
    """Mutable order fields (the queue only advances status and progress)."""

    status: CraftingOrderStatus | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    completed_at: datetime | None = None


class CraftingOrderRead(SQLModel):
    """One queued or finished workshop order."""

    id: UUID4
    room_id: UUID4
    item_name: str
    item_type: str
    rarity: RarityEnum
    status: CraftingOrderStatus
    progress: float
    started_at: datetime
    estimated_completion_at: datetime
    completed_at: datetime | None = None
    junk_spent: int
    caps_spent: int
    required_stat: str
    ability_sum_at_start: int


class CraftingOrdersRead(SQLModel):
    orders: list[CraftingOrderRead] = []
