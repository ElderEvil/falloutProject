import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type ExplorationRead = components['schemas']['ExplorationRead']

export const explorationApi = {
  /**
   * Dispatch a party to clear a map point (issue 772, phase 3).
   * The point is cleared server-side when the expedition completes.
   */
  async dispatchToLocation(
    token: string,
    vaultId: string,
    payload: { dwellerIds: string[]; locationId: string }
  ): Promise<ExplorationRead> {
    const response = await axios.post<ExplorationRead>(
      `/api/v1/explorations/dispatch?vault_id=${vaultId}`,
      { dweller_ids: payload.dwellerIds, location_id: payload.locationId },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    return response.data
  },
}
