import { apiGet, apiPost } from '@/core/utils/api'
import type { DwellerDead, DwellerReviveResponse, RevivalCostResponse } from '../models/dweller'

export function getDeadDwellers(vaultId: string): Promise<DwellerDead[]> {
  return apiGet<DwellerDead[]>(`/api/v1/dwellers/vault/${vaultId}/dead`)
}

export function getGraveyardDwellers(vaultId: string): Promise<DwellerDead[]> {
  return apiGet<DwellerDead[]>(`/api/v1/dwellers/vault/${vaultId}/graveyard`)
}

export function getRevivalCost(dwellerId: string): Promise<RevivalCostResponse> {
  return apiGet<RevivalCostResponse>(`/api/v1/dwellers/${dwellerId}/revival_cost`)
}

export function reviveDweller(dwellerId: string): Promise<DwellerReviveResponse> {
  return apiPost<DwellerReviveResponse>(`/api/v1/dwellers/${dwellerId}/revive`)
}
