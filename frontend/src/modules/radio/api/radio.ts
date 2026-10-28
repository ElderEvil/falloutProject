import { apiGet, apiPost, apiPut } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

export type RadioMode = 'recruitment' | 'happiness'
export type RadioModeResponse = components['schemas']['RadioModeResponse']
export type RadioStatsRead = components['schemas']['RadioStatsRead']
export type ManualRecruitRequest = components['schemas']['ManualRecruitRequest']
export type RecruitmentResponse = components['schemas']['RecruitmentResponse']

/** Switch a vault's radio between recruitment and happiness mode. */
export async function setRadioMode(vaultId: string, mode: RadioMode): Promise<string> {
  const response = await apiPut<RadioModeResponse>(
    `/api/v1/radio/vault/${vaultId}/mode`,
    undefined,
    {
      params: { mode },
    }
  )
  return response.radio_mode
}

/** Read a vault's radio recruitment statistics. */
export function getRadioStats(vaultId: string): Promise<RadioStatsRead> {
  return apiGet<RadioStatsRead>(`/api/v1/radio/vault/${vaultId}/stats`)
}

/** Spend caps to recruit a dweller through the radio room. */
export function recruitDweller(
  vaultId: string,
  payload: ManualRecruitRequest = {}
): Promise<RecruitmentResponse> {
  return apiPost<RecruitmentResponse>(`/api/v1/radio/vault/${vaultId}/recruit`, payload)
}

export const radioApi = {
  getStats: getRadioStats,
  setMode: setRadioMode,
  recruit: recruitDweller,
}
