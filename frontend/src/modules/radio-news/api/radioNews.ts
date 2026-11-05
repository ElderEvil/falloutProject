import { apiGet, apiPost } from '@/core/utils/api'
import type { ApiRequestOptions } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

export type RadioNewsBroadcast = components['schemas']['BroadcastRead']

/** Fetch today's broadcast; the server generates it on the first call of the UTC day. */
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
