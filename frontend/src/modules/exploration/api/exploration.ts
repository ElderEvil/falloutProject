import { apiGet, apiPost } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

export type ExplorationRead = components['schemas']['ExplorationRead']
export type ExplorationReadShort = components['schemas']['ExplorationReadShort']
export type ExplorationSendRequest = components['schemas']['ExplorationSendRequest']
export type ExplorationProgress = components['schemas']['ExplorationProgress']
export type ExplorationCompleteResponse = components['schemas']['ExplorationCompleteResponse']
export type PendingOverflowRead = components['schemas']['PendingOverflowRead']
export type OverflowActionResponse = components['schemas']['OverflowActionResponse']

export type ExplorationPartyMember = components['schemas']['ExplorationPartyMemberRead']

export const explorationApi = {
  /**
   * Dispatch a party to clear a map point (issue 772, phase 3).
   * The point is cleared server-side when the expedition completes.
   */
  async dispatchToLocation(
    vaultId: string,
    payload: { dwellerIds: string[]; locationId: string; stimpaks?: number; radaways?: number }
  ): Promise<ExplorationRead> {
    return apiPost<ExplorationRead>(
      '/api/v1/explorations/dispatch',
      {
        dweller_ids: payload.dwellerIds,
        location_id: payload.locationId,
        stimpaks: payload.stimpaks ?? 0,
        radaways: payload.radaways ?? 0,
      },
      { params: { vault_id: vaultId } }
    )
  },

  /** Ask the server for an auto departure heading; null when the vault has no map placement. */
  async suggestHeading(vaultId: string, seed: string, duration: number): Promise<number | null> {
    const response = await apiGet<{ heading_degrees?: number | null }>(
      '/api/v1/explorations/suggest-heading',
      { params: { vault_id: vaultId, seed, duration } }
    )
    return response.heading_degrees ?? null
  },

  /** Fetch the dispatch party for an exploration, slot-ordered; empty for a free-roam run. */
  async getExplorationParty(
    vaultId: string,
    explorationId: string
  ): Promise<ExplorationPartyMember[]> {
    return apiGet<ExplorationPartyMember[]>(
      `/api/v1/explorations/vault/${vaultId}/${explorationId}/party`
    )
  },

  /** Send a single dweller out; the payload carries the roster/destination shape. */
  async sendDwellerToWasteland(
    vaultId: string,
    payload: ExplorationSendRequest
  ): Promise<ExplorationRead> {
    return apiPost<ExplorationRead>('/api/v1/explorations/send', payload, {
      params: { vault_id: vaultId },
    })
  },

  /** List a vault's explorations, optionally narrowed to active/returning runs. */
  async getExplorationsByVault(
    vaultId: string,
    activeOnly: boolean
  ): Promise<ExplorationReadShort[]> {
    return apiGet<ExplorationReadShort[]>(`/api/v1/explorations/vault/${vaultId}`, {
      params: { active_only: activeOnly },
    })
  },

  /** Fetch one exploration, including completed runs absent from the active-only list. */
  async getExploration(explorationId: string): Promise<ExplorationRead> {
    return apiGet<ExplorationRead>(`/api/v1/explorations/${explorationId}`)
  },

  /** Fetch the current progress snapshot used by the detail and polling surfaces. */
  async getExplorationProgress(explorationId: string): Promise<ExplorationProgress> {
    return apiGet<ExplorationProgress>(`/api/v1/explorations/${explorationId}/progress`)
  },

  /** Recall a dweller; the response carries the updated run and any early-return rewards. */
  async recallDweller(explorationId: string): Promise<ExplorationCompleteResponse> {
    return apiPost<ExplorationCompleteResponse>(`/api/v1/explorations/${explorationId}/recall`, {})
  },

  /** Complete a run that has reached its duration; returns the run and rewards. */
  async completeExploration(explorationId: string): Promise<ExplorationCompleteResponse> {
    return apiPost<ExplorationCompleteResponse>(
      `/api/v1/explorations/${explorationId}/complete`,
      {}
    )
  },

  /**
   * Resolve one held overflow item. The reward modal explains a legacy 404, so the
   * request opts out of the interceptor's duplicate error toast.
   */
  async resolveOverflowItem(
    explorationId: string,
    action: 'take' | 'sell',
    index: number
  ): Promise<OverflowActionResponse> {
    return apiPost<OverflowActionResponse>(
      `/api/v1/explorations/${explorationId}/overflow/${action}`,
      { index },
      { skipErrorNotification: true }
    )
  },

  /** Unresolved exploration loot that the return screen still needs to surface. */
  async getPendingOverflow(vaultId: string): Promise<PendingOverflowRead[]> {
    return apiGet<PendingOverflowRead[]>(`/api/v1/explorations/vault/${vaultId}/pending-overflow`)
  },
}
