"""Recipe unlock service: learn a gated crafting recipe by scrapping the exact item.

v1 unlocks only through scrapping. Quest/objective unlocking is intentionally not
built yet; it can reuse the already-emitted QUEST_COMPLETED / OBJECTIVE_COMPLETED
events plus a catalog ``craft.unlock.quest`` / ``.objective`` spec, without a
RewardType or PG-enum change.
"""

import logging
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core import db_locks
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.db.session import async_session_maker
from app.services.exploration import data_loader

logger = logging.getLogger(__name__)

_ITEM_TYPE_LOADERS = {
    "weapon": data_loader.load_weapons,
    "outfit": data_loader.load_outfits,
}


def catalog_entry(item_type: str, name: str) -> dict[str, Any] | None:
    """The item catalog entry for a workshop item, matched case-insensitively by name."""
    loader = _ITEM_TYPE_LOADERS.get(item_type)
    if loader is None or not name:
        return None
    target = name.strip().lower()
    return next((entry for entry in loader() if str(entry.get("name", "")).strip().lower() == target), None)


def scrap_unlock_count(entry: dict[str, Any]) -> int:
    """Scraps needed to learn a recipe: catalog override, else the rarity default, else 0."""
    override = ((entry.get("craft") or {}).get("unlock") or {}).get("scrap") or {}
    if "count" in override:
        return int(override["count"])
    return game_config.crafting.scrap_unlock_count(str(entry.get("rarity", "")))


def is_gated(entry: dict[str, Any] | None) -> bool:
    """True when the recipe must be learned before it can be crafted."""
    return entry is not None and scrap_unlock_count(entry) > 0


def unlock_hint(entry: dict[str, Any] | None) -> str | None:
    """Player-facing hint on how to learn a gated recipe, or None when it needs no learning."""
    if entry is None:
        return None
    count = scrap_unlock_count(entry)
    if count <= 0:
        return None
    name = str(entry.get("name", "")).strip()
    phrase = f"a {name}" if count == 1 else f"{count}\u00d7 {name}"
    return f"Scrap {phrase} to reverse-engineer this schematic"


class RecipeUnlockService:
    """Reads and advances per-vault recipe unlock progress."""

    async def is_unlocked(
        self, db_session: AsyncSession, *, vault_id: UUID4, item_type: str, entry: dict[str, Any]
    ) -> bool:
        """True when the recipe is ungated or the vault has already unlocked it.

        Takes the catalog entry the caller already resolved, so ordering a recipe
        never rescans the catalog.
        """
        if not is_gated(entry):
            return True
        row = await crud.vault_recipe_unlock.get_for_vault(db_session, vault_id, item_type, str(entry["name"]))
        return row is not None and row.unlocked_at is not None

    async def record_scrap(
        self, db_session: AsyncSession, *, vault_id: UUID4, item_type: str, item_name: str
    ) -> dict[str, Any] | None:
        """Advance unlock progress for a scrapped item.

        Returns the unlocked recipe payload when this scrap completed the recipe,
        otherwise None. Ungated items are ignored.
        """
        entry = catalog_entry(item_type, item_name)
        if entry is None:
            return None
        count = scrap_unlock_count(entry)
        if count <= 0:
            return None

        recipe_name = str(entry["name"])
        # Serialize the counter across workers: the bus only serializes scraps within one process.
        await db_locks.advisory_xact_lock(db_session, f"recipe_unlock:{vault_id}:{item_type}:{recipe_name}")
        newly_unlocked = await crud.vault_recipe_unlock.record_scrap(
            db_session,
            vault_id=vault_id,
            item_type=item_type,
            recipe_name=recipe_name,
            threshold=count,
        )
        if not newly_unlocked:
            return None
        return {"item_type": item_type, "recipe_name": recipe_name}


recipe_unlock_service = RecipeUnlockService()


async def _notify_unlock(db_session: AsyncSession, vault_id: UUID4, unlocked: dict[str, Any]) -> None:
    """Tell the vault owner they just learned a recipe."""
    from app.crud.vault import vault as vault_crud
    from app.services.notification_service import notification_service

    vault = await vault_crud.get_or_none(db_session, id=vault_id)
    if vault is None:
        return
    await notification_service.notify_recipe_unlocked(
        db_session,
        user_id=vault.user_id,
        vault_id=vault_id,
        item_type=unlocked["item_type"],
        recipe_name=unlocked["recipe_name"],
    )


async def _on_item_scrapped(_event_type: str, vault_id: UUID4, data: dict[str, Any]) -> None:
    """Learn a gated recipe once its item has been scrapped enough times."""
    item_type = data.get("item_type")
    item_name = data.get("item_name")
    if not item_type or not item_name:
        return

    # Dramatiq ticks bind a loop-local maker so handlers never reuse the module-global
    # asyncpg connection across worker event loops.
    from app.services.progression.objectives.evaluators import current_session_maker

    session_maker = current_session_maker.get() or async_session_maker
    async with session_maker() as db_session:
        try:
            unlocked = await recipe_unlock_service.record_scrap(
                db_session, vault_id=vault_id, item_type=item_type, item_name=str(item_name)
            )
            # Commit below-threshold progress too, or a multi-scrap counter never advances.
            await db_session.commit()
            if unlocked is None:
                return
            await event_bus.emit(GameEvent.RECIPE_UNLOCKED, vault_id, unlocked)
            await _notify_unlock(db_session, vault_id, unlocked)
            logger.info(f"Recipe '{unlocked['recipe_name']}' unlocked for vault {vault_id}")
        except Exception:
            logger.exception(f"Failed to process ITEM_SCRAPPED for vault {vault_id}")


def register_recipe_unlock_handlers() -> None:
    """Subscribe the recipe-unlock handler to scrapping."""
    event_bus.subscribe(GameEvent.ITEM_SCRAPPED, _on_item_scrapped)
    logger.info("Registered handler for ITEM_SCRAPPED event")
