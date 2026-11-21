import { apiGet, apiPost } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

export type WorldEvent = components['schemas']['WorldEventRead']
export type WorldEventClaim = components['schemas']['WorldEventClaimRead']

const base = (vaultId: string) => `/api/v1/vaults/${vaultId}/world-event`

/** Current (or latest) world event plus this vault's standing. */
const getEvent = (vaultId: string) => apiGet<WorldEvent>(base(vaultId))

/** Pay the completed event's reward list exactly once. */
const claim = (vaultId: string) => apiPost<WorldEventClaim>(`${base(vaultId)}/claim`)

export const worldEventService = { getEvent, claim }
