import { apiGet, apiPost } from '@/core/utils/api'
import type { TradeMarketResponse, TradeResultResponse } from '../models/trading'

/** Fetch the Trading Post market: offers from other vaults, own listings, caps. */
async function getMarket(vaultId: string): Promise<TradeMarketResponse> {
  return apiGet<TradeMarketResponse>(`/api/v1/vaults/${vaultId}/trading-post/market`)
}

/** Sell a soft-deleted dweller from the vault for caps (single-use sale). */
async function sellDweller(vaultId: string, dwellerId: string): Promise<TradeResultResponse> {
  return apiPost<TradeResultResponse>(`/api/v1/vaults/${vaultId}/trading-post/sell`, null, {
    params: { dweller_id: dwellerId },
  })
}

/** Buy a soft-deleted dweller listed by another vault, recycling it into the vault. */
async function buyDweller(vaultId: string, dwellerId: string): Promise<TradeResultResponse> {
  return apiPost<TradeResultResponse>(`/api/v1/vaults/${vaultId}/trading-post/buy`, null, {
    params: { dweller_id: dwellerId },
  })
}

export const tradingService = { getMarket, sellDweller, buyDweller }
