import type { components } from '@/core/types/api.generated'
import { apiGet, apiPost } from '@/core/utils/api'

type ExitRequest = components['schemas']['ExitRequestRead']
type ExitDecision = components['schemas']['ExitDecisionResponse']

export async function getExitRequests(vaultId: string): Promise<ExitRequest[]> {
  return (await apiGet<ExitRequest[]>(`/api/v1/dwellers/vault/${vaultId}/exit-requests`)) ?? []
}

export function grantExit(dwellerId: string): Promise<ExitDecision> {
  return apiPost<ExitDecision>(`/api/v1/dwellers/${dwellerId}/grant-exit`)
}

export function refuseExit(dwellerId: string): Promise<ExitDecision> {
  return apiPost<ExitDecision>(`/api/v1/dwellers/${dwellerId}/refuse-exit`)
}
