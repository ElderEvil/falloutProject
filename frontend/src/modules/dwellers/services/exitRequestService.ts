import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type ExitRequest = components['schemas']['ExitRequestRead']
export type ExitDecision = components['schemas']['ExitDecisionResponse']

/** Dwellers currently waiting on an answer to their request to leave the vault. */
export async function fetchExitRequests(vaultId: string, token: string): Promise<ExitRequest[]> {
  const response = await axios.get<components['schemas']['ExitRequestListResponse']>(
    `/api/v1/vaults/${vaultId}/exit-requests`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data.requests ?? []
}

/** Let the dweller go. Permanent: they never return and cannot be revived. */
export async function grantExit(
  vaultId: string,
  dwellerId: string,
  token: string
): Promise<ExitDecision> {
  const response = await axios.post<ExitDecision>(
    `/api/v1/vaults/${vaultId}/exit-requests/${dwellerId}/grant`,
    null,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}

/** Refuse the ask. The dweller takes a happiness hit and the request stands. */
export async function refuseExit(
  vaultId: string,
  dwellerId: string,
  token: string
): Promise<ExitDecision> {
  const response = await axios.post<ExitDecision>(
    `/api/v1/vaults/${vaultId}/exit-requests/${dwellerId}/refuse`,
    null,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}
