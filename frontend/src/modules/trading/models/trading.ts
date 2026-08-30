import type { DwellerShort } from '@/modules/dwellers/models/dweller'

export interface TradeOffer {
  dweller: DwellerShort
  price: number
  has_bio: boolean
  places_visited: number
}

export interface TradeMarketResponse {
  market_offers: TradeOffer[]
  my_listings: TradeOffer[]
  bottle_caps: number
}

export interface TradeResultResponse {
  dweller_id: string
  price: number
  bottle_caps: number
}
