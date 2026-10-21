import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type AvailableSiteView = components['schemas']['AvailableSiteView']
export type SiteAvailabilityView = components['schemas']['SiteAvailabilityView']
export type ExplorationSiteOpportunityView = components['schemas']['ExplorationSiteOpportunityView']
export type SiteRoomView = components['schemas']['SiteRoomView']

export const expeditionSiteApi = {
  async getAvailability(explorationId: string): Promise<SiteAvailabilityView> {
    const response = await axios.get<SiteAvailabilityView>(
      `/api/v1/explorations/${explorationId}/site/available`
    )
    return response.data
  },

  async getVaultOpportunities(vaultId: string): Promise<ExplorationSiteOpportunityView[]> {
    const response = await axios.get<ExplorationSiteOpportunityView[]>(
      `/api/v1/explorations/vault/${vaultId}/site/opportunities`
    )
    return response.data
  },

  async enterSite(explorationId: string, siteId: string): Promise<SiteRoomView> {
    const response = await axios.post<SiteRoomView>(
      `/api/v1/explorations/${explorationId}/site/enter`,
      { site_id: siteId }
    )
    return response.data
  },

  async getCurrentRoom(explorationId: string): Promise<SiteRoomView | null> {
    const response = await axios.get<SiteRoomView | null>(
      `/api/v1/explorations/${explorationId}/site`
    )
    return response.data
  },

  async resolveNode(explorationId: string, choiceId?: string): Promise<SiteRoomView> {
    const response = await axios.post<SiteRoomView>(
      `/api/v1/explorations/${explorationId}/site/resolve`,
      choiceId === undefined ? {} : { choice_id: choiceId }
    )
    return response.data
  },

  async retreatSite(explorationId: string): Promise<SiteRoomView> {
    const response = await axios.post<SiteRoomView>(
      `/api/v1/explorations/${explorationId}/site/retreat`
    )
    return response.data
  },
}
