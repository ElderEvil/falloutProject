import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type ExplorationRead = components['schemas']['ExplorationRead']
export type ExplorationSendRequest = components['schemas']['ExplorationSendRequest']

/** Hand-written `ExplorationPartyMemberRead` shape (backend was offline, so the OpenAPI client was not regenerated). */
export interface ExplorationPartyMember {
  id: string
  exploration_id: string
  vault_id: string
  dweller_id: string
  slot_number: number
  status: string
  created_at: string | null
  updated_at: string | null
}

export const explorationApi = {
  /**
   * Dispatch a party to clear a map point (issue 772, phase 3).
   * The point is cleared server-side when the expedition completes.
   */
  async dispatchToLocation(
    token: string,
    vaultId: string,
    payload: { dwellerIds: string[]; locationId: string; stimpaks?: number; radaways?: number }
  ): Promise<ExplorationRead> {
    const response = await axios.post<ExplorationRead>(
      `/api/v1/explorations/dispatch?vault_id=${vaultId}`,
      {
        dweller_ids: payload.dwellerIds,
        location_id: payload.locationId,
        stimpaks: payload.stimpaks ?? 0,
        radaways: payload.radaways ?? 0,
      },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    return response.data
  },

  /** Ask the server for an auto departure heading; null when the vault has no map placement. */
  async suggestHeading(
    token: string,
    vaultId: string,
    seed: string,
    duration: number
  ): Promise<number | null> {
    const response = await axios.get<{ heading_degrees: number | null }>(
      '/api/v1/explorations/suggest-heading',
      {
        params: { vault_id: vaultId, seed, duration },
        headers: { Authorization: `Bearer ${token}` },
      }
    )
    return response.data.heading_degrees
  },

  /** Fetch the dispatch party for an exploration, slot-ordered; empty for a free-roam run. */
  async getExplorationParty(
    vaultId: string,
    explorationId: string
  ): Promise<ExplorationPartyMember[]> {
    const response = await axios.get<ExplorationPartyMember[]>(
      `/api/v1/explorations/vault/${vaultId}/${explorationId}/party`
    )
    return response.data
  },
}
