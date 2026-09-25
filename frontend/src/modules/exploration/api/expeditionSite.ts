import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type AvailableSiteView = components['schemas']['AvailableSiteView']
export type SiteRoomView = components['schemas']['SiteRoomView']

export const expeditionSiteApi = {
  async listAvailableSites(explorationId: string): Promise<AvailableSiteView[]> {
    const response = await axios.get<AvailableSiteView[]>(
      `/api/v1/explorations/${explorationId}/site/available`
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
