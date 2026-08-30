"""Trading Post service (PoC).

A market where soft-deleted dwellers are the commodity: vaults sell their
soft-deleted dwellers for caps and buy soft-deleted dwellers listed by other
vaults. Buying reuses the recycling pipeline (stats reset, relationships
cleared) so traded dwellers arrive as fresh recruits.
"""

import logging

from pydantic import UUID4
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.wasteland_location import DwellerLocation, DwellerLocationRelationEnum
from app.schemas.common import RarityEnum
from app.schemas.dweller import DwellerReadLess
from app.schemas.trading import TradeMarketResponse, TradeOffer, TradeResultResponse
from app.services.dweller_recycling_service import dweller_recycling_service
from app.utils.exceptions import ResourceNotFoundException, VaultOperationException

logger = logging.getLogger(__name__)

MARKET_SIZE = 20

_RARITY_BASE_VALUE: dict[RarityEnum, int] = {
    RarityEnum.COMMON: 50,
    RarityEnum.RARE: 150,
    RarityEnum.LEGENDARY: 400,
}


def trade_value(dweller: Dweller) -> int:
    """Caps a dweller trades for: rarity base plus a per-level bonus."""
    return _RARITY_BASE_VALUE.get(dweller.rarity, _RARITY_BASE_VALUE[RarityEnum.COMMON]) + dweller.level * 10


def _to_offer(dweller: Dweller, places_visited: int) -> TradeOffer:
    return TradeOffer(
        dweller=DwellerReadLess.model_validate(dweller),
        price=trade_value(dweller),
        has_bio=bool(dweller.bio),
        places_visited=places_visited,
    )


async def _visited_counts(db_session: AsyncSession, dweller_ids: list[UUID4]) -> dict[UUID4, int]:
    """Count VISITED wasteland locations per dweller in one query."""
    if not dweller_ids:
        return {}
    query = (
        select(DwellerLocation.dweller_id, func.count())
        .where(col(DwellerLocation.dweller_id).in_(dweller_ids))
        .where(DwellerLocation.relation == DwellerLocationRelationEnum.VISITED)
        .group_by(DwellerLocation.dweller_id)
    )
    result = await db_session.execute(query)
    return {row[0]: row[1] for row in result.all()}


async def _get_tradable(db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
    """Fetch a soft-deleted, non-dead dweller by id."""
    query = (
        select(Dweller)
        .where(Dweller.id == dweller_id)
        .where(col(Dweller.is_deleted).is_(True))
        .where(col(Dweller.is_dead).is_(False))
    )
    result = await db_session.execute(query)
    dweller = result.scalars().one_or_none()
    if not dweller:
        raise ResourceNotFoundException(Dweller, identifier=dweller_id)
    return dweller


class TradingPostService:
    """PoC market operations for soft-deleted dwellers."""

    async def get_market(self, db_session: AsyncSession, vault: Vault) -> TradeMarketResponse:
        """List dwellers other vaults have put on the market plus own listings."""
        market_query = (
            select(Dweller)
            .where(col(Dweller.is_deleted).is_(True))
            .where(col(Dweller.is_dead).is_(False))
            .where(Dweller.vault_id != vault.id)
            .order_by(col(Dweller.deleted_at).desc())
            .limit(MARKET_SIZE)
            .options(selectinload(Dweller.weapon))
        )
        market_result = await db_session.execute(market_query)

        listings_query = (
            select(Dweller)
            .where(Dweller.vault_id == vault.id)
            .where(col(Dweller.is_deleted).is_(True))
            .where(col(Dweller.is_dead).is_(False))
            .order_by(col(Dweller.deleted_at).desc())
            .options(selectinload(Dweller.weapon))
        )
        listings_result = await db_session.execute(listings_query)

        market_dwellers = list(market_result.scalars().all())
        listing_dwellers = list(listings_result.scalars().all())
        visited = await _visited_counts(db_session, [d.id for d in market_dwellers] + [d.id for d in listing_dwellers])

        return TradeMarketResponse(
            market_offers=[_to_offer(d, visited.get(d.id, 0)) for d in market_dwellers],
            my_listings=[_to_offer(d, visited.get(d.id, 0)) for d in listing_dwellers],
            bottle_caps=vault.bottle_caps,
        )

    async def sell_dweller(self, db_session: AsyncSession, vault: Vault, dweller_id: UUID4) -> TradeResultResponse:
        """Sell one of the vault's soft-deleted dwellers for caps."""
        dweller = await _get_tradable(db_session, dweller_id)
        if dweller.vault_id != vault.id:
            raise VaultOperationException(detail="Dweller does not belong to this vault")

        price = trade_value(dweller)
        await vault_crud.deposit_caps(db_session=db_session, vault_obj=vault, amount=price)

        logger.info("Trading Post: vault %s sold dweller %s for %d caps", vault.id, dweller_id, price)
        return TradeResultResponse(dweller_id=dweller_id, price=price, bottle_caps=vault.bottle_caps)

    async def buy_dweller(self, db_session: AsyncSession, vault: Vault, dweller_id: UUID4) -> TradeResultResponse:
        """Buy a soft-deleted dweller from another vault; caps go to the seller."""
        dweller = await _get_tradable(db_session, dweller_id)
        if dweller.vault_id == vault.id:
            raise VaultOperationException(detail="Dweller is already owned by this vault")

        price = trade_value(dweller)
        seller_vault = await vault_crud.get(db_session, dweller.vault_id)
        if not seller_vault:
            raise ResourceNotFoundException(Vault, identifier=dweller.vault_id)

        await vault_crud.withdraw_caps(db_session=db_session, vault_obj=vault, amount=price)
        await vault_crud.deposit_caps(db_session=db_session, vault_obj=seller_vault, amount=price)

        recycled = await dweller_recycling_service.recycle_dweller_for_vault(
            db_session=db_session,
            dweller_id=dweller_id,
            target_vault_id=vault.id,
            reset_stats=True,
        )

        logger.info(
            "Trading Post: vault %s bought dweller %s from vault %s for %d caps",
            vault.id,
            dweller_id,
            seller_vault.id,
            price,
        )
        return TradeResultResponse(dweller_id=recycled.id, price=price, bottle_caps=vault.bottle_caps)


# Singleton instance
trading_post_service = TradingPostService()
