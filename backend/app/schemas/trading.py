"""Schemas for the Trading Post (PoC: trading soft-deleted dwellers)."""

from pydantic import UUID4, BaseModel

from app.schemas.dweller import DwellerReadLess


class TradeOffer(BaseModel):
    """A soft-deleted dweller listed for trade, with its computed price and highlights."""

    dweller: DwellerReadLess
    price: int
    has_bio: bool = False
    places_visited: int = 0


class TradeMarketResponse(BaseModel):
    """Trading Post overview: market offers, own listings, and vault caps."""

    market_offers: list[TradeOffer]
    my_listings: list[TradeOffer]
    bottle_caps: int


class TradeResultResponse(BaseModel):
    """Result of a sell/buy trade."""

    dweller_id: UUID4
    price: int
    bottle_caps: int
