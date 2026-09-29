from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel


class VaultRecipeUnlock(SQLModel, table=True):
    """Per-vault unlock progress for a gated crafting recipe.

    A row exists only for recipes the vault has worked toward; absence means the
    recipe is ungated. ``unlocked_at`` stays null until the scrapped count reaches
    the recipe's threshold.
    """

    vault_id: UUID4 = Field(foreign_key="vault.id", primary_key=True)
    item_type: str = Field(primary_key=True, max_length=16)
    recipe_name: str = Field(primary_key=True, max_length=128)
    progress: int = Field(default=0, ge=0)
    unlocked_at: datetime | None = Field(default=None)
    source: str = Field(default="scrap", max_length=16)
