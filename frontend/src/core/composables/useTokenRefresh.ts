import { ensureAccessToken } from '@/core/utils/authSession'
import { usePolling } from './usePolling'

/** Proactive refresh shares authentication, visibility and retry rules with data polling. */
export function useTokenRefresh() {
  return usePolling(ensureAccessToken, { interval: 60_000 })
}
