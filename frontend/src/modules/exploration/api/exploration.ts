import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type ExplorationRead = components['schemas']['ExplorationRead']
export type ExplorationSendRequest = components['schemas']['ExplorationSendRequest']

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
}
