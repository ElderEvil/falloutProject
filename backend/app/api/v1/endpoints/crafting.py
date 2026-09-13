"""Crafting endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.schemas.crafting import (
    CraftingOrderRead,
    CraftingOrdersRead,
    CraftingRecipesRead,
    CraftRequest,
    CraftResultRead,
)
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


@router.get("/vault/{vault_id}/orders", response_model=CraftingOrdersRead)
async def list_crafting_orders(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> CraftingOrdersRead:
    """List every workshop order for a vault, newest first.

    Returns:
        The vault's crafting queue.

    Raises:
        HTTPException: 403 if user lacks access to the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    orders = await crafting_service.list_orders(db_session, vault_id)
    return CraftingOrdersRead(orders=[CraftingOrderRead.model_validate(order) for order in orders])


@router.post("/vault/{vault_id}/orders", response_model=CraftingOrderRead, status_code=201)
async def start_crafting_order(
    vault_id: UUID4,
    request: CraftRequest,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> CraftingOrderRead:
    """Queue a craft at its workshop, consuming materials immediately.

    Returns:
        The queued order.

    Raises:
        HTTPException: 403 if user lacks access to the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    order = await crafting_service.start_order(db_session, vault_id, request.item_name, request.item_type)
    return CraftingOrderRead.model_validate(order)


@router.post("/vault/{vault_id}/orders/{order_id}/collect", response_model=CraftResultRead)
async def collect_crafting_order(
    vault_id: UUID4,
    order_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
) -> CraftResultRead:
    """Move a finished order's item into storage.

    Returns:
        The crafted item and the materials it consumed.

    Raises:
        HTTPException: 403 if user lacks access to the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crafting_service.collect_order(db_session, vault_id, order_id)
