import axios from '@/core/plugins/axios'
import type { TradeMarketResponse, TradeResultResponse } from '../models/trading'

async function getMarket(vaultId: string, token: string): Promise<TradeMarketResponse> {
  const response = await axios.get<TradeMarketResponse>(`/api/v1/vaults/${vaultId}/trading-post/market`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

async function sellDweller(vaultId: string, dwellerId: string, token: string): Promise<TradeResultResponse> {
  const response = await axios.post<TradeResultResponse>(`/api/v1/vaults/${vaultId}/trading-post/sell`, null, {
    params: { dweller_id: dwellerId },
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

async function buyDweller(vaultId: string, dwellerId: string, token: string): Promise<TradeResultResponse> {
  const response = await axios.post<TradeResultResponse>(`/api/v1/vaults/${vaultId}/trading-post/buy`, null, {
    params: { dweller_id: dwellerId },
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export const tradingService = { getMarket, sellDweller, buyDweller }
