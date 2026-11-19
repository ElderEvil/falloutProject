import type { components } from '@/core/types/api.generated'
import { apiGet, apiPost } from '@/core/utils/api'

export type AvailableSiteView = components['schemas']['AvailableSiteView']
export type SiteRoomView = components['schemas']['SiteRoomView']

export const expeditionSiteApi = {
  async listAvailableSites(explorationId: string): Promise<AvailableSiteView[]> {
    return apiGet<AvailableSiteView[]>(`/api/v1/explorations/${explorationId}/site/available`)
  },

  async enterSite(explorationId: string, siteId: string): Promise<SiteRoomView> {
    return apiPost<SiteRoomView>(`/api/v1/explorations/${explorationId}/site/enter`, {
      site_id: siteId,
    })
  },

  async getCurrentRoom(explorationId: string): Promise<SiteRoomView | null> {
    return apiGet<SiteRoomView | null>(`/api/v1/explorations/${explorationId}/site`)
  },

  async resolveNode(
    explorationId: string,
    choiceId?: string,
    useSkill = false,
    expectedRound?: number,
    questionId?: string
  ): Promise<SiteRoomView> {
    return apiPost<SiteRoomView>(`/api/v1/explorations/${explorationId}/site/resolve`, {
      ...(choiceId === undefined ? {} : { choice_id: choiceId }),
      ...(questionId === undefined ? {} : { question_id: questionId }),
      ...(useSkill ? { use_skill: true } : {}),
      ...(expectedRound === undefined ? {} : { expected_round: expectedRound }),
    })
  },

  async retreatSite(explorationId: string): Promise<SiteRoomView> {
    return apiPost<SiteRoomView>(`/api/v1/explorations/${explorationId}/site/retreat`)
  },
}
