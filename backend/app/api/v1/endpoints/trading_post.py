"""Trading Post endpoints (PoC): trade soft-deleted dwellers for caps."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_user_vault_or_403
from app.db.session import get_async_session
from app.models.vault import Vault
from app.schemas.trading import TradeMarketResponse, TradeResultResponse
from app.services.trading_post_service import trading_post_service

router = APIRouter(prefix="/vaults/{vault_id}/trading-post", tags=["trading-post"])


@router.get("/market", response_model=TradeMarketResponse)
async def get_trading_market(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TradeMarketResponse:
    """List soft-deleted dwellers on the market plus this vault's own listings."""
    return await trading_post_service.get_market(db_session, vault)


@router.post("/sell", response_model=TradeResultResponse)
async def sell_dweller(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    dweller_id: UUID4,
) -> TradeResultResponse:
    """Sell one of this vault's soft-deleted dwellers for caps."""
    return await trading_post_service.sell_dweller(db_session, vault, dweller_id)


@router.post("/buy", response_model=TradeResultResponse)
async def buy_dweller(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    dweller_id: UUID4,
) -> TradeResultResponse:
    """Buy a soft-deleted dweller listed by another vault; caps go to the seller."""
    return await trading_post_service.buy_dweller(db_session, vault, dweller_id)
