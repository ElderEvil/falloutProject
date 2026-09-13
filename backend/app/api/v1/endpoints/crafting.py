"""Crafting endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.schemas.crafting import CraftingRecipesRead, CraftRequest, CraftResultRead
from app.services.crafting_service import crafting_service

router = APIRouter(prefix="/crafting", tags=["Crafting"])
logger = logging.getLogger(__name__)


@router.get("/vault/{vault_id}/recipes/{item_type}", response_model=CraftingRecipesRead)
async def list_crafting_recipes(
    vault_id: UUID4,
    item_type: str,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> CraftingRecipesRead:
    """List craftable items of one type with their costs and affordability.

    Returns:
        Recipe list for the vault's workshop.

    Raises:
        HTTPException: 403 if user lacks access to the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    recipes = await crafting_service.list_recipes(db_session, vault_id, item_type)
    logger.info("Crafting recipes listed", extra={"vault_id": str(vault_id), "item_type": item_type})
    return CraftingRecipesRead(recipes=recipes)


@router.post("/vault/{vault_id}/craft", response_model=CraftResultRead)
async def craft_item(
    vault_id: UUID4,
    request: CraftRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> CraftResultRead:
    """Craft one catalog item at its matching workshop.

    Returns:
        The crafted item and the materials spent.

    Raises:
        HTTPException: 403 if user lacks access to the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crafting_service.craft(db_session, vault_id, request.item_name, request.item_type)
