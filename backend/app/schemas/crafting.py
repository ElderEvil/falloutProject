"""Schemas for instant crafting at the weapon and outfit workshops."""

from typing import Literal

from pydantic import UUID4, Field
from sqlmodel import SQLModel

from app.core.enums import RarityEnum

CraftableItemType = Literal["weapon", "outfit"]


class CraftingRecipeRead(SQLModel):
    """One craftable catalog entry with its cost and current affordability."""

    name: str
    item_type: CraftableItemType
    rarity: RarityEnum
    value: int | None = None
    junk_cost: int
    caps_cost: int
    can_craft: bool
    missing_junk: int = 0


class CraftRequest(SQLModel):
    """Craft one catalog item at its matching workshop."""

    item_name: str = Field(min_length=1, max_length=64)
    item_type: CraftableItemType


class CraftResultRead(SQLModel):
    """The crafted item plus the materials that were spent."""

    item_type: CraftableItemType
    item_id: UUID4
    name: str
    rarity: RarityEnum
    junk_spent: int
    caps_spent: int


class CraftingRecipesRead(SQLModel):
    """Recipe list for a vault's workshops."""

    recipes: list[CraftingRecipeRead] = []
