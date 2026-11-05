import { apiGet, apiPost } from '@/core/utils/api'
import type { ApiRequestOptions } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

export type RadioNewsBroadcast = components['schemas']['BroadcastRead']

/** Switch the vault radio between recruitment and happiness mode. */
export async function fetchRadioNews(
  vaultId: string,
  options: ApiRequestOptions = {}
): Promise<RadioNewsBroadcast> {
  return apiGet<RadioNewsBroadcast>(`/api/v1/vaults/${vaultId}/radio-news`, options)
}

/** Regenerate (re-render) the daily broadcast; rate-limited to 3/UTC day. */
export async function regenerateRadioNews(
  vaultId: string,
  options: ApiRequestOptions = {}
): Promise<RadioNewsBroadcast> {
  return apiPost<RadioNewsBroadcast>(`/api/v1/vaults/${vaultId}/radio-news/regenerate`, undefined, options)
}
