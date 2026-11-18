import { apiGet, apiPut } from '@/core/utils/api'
import type { ContaminationTeamRead, HazardTeam } from '../models/contaminationTeam'

export const contaminationTeamApi = {
  async getRoster(vaultId: string): Promise<ContaminationTeamRead> {
    return apiGet<ContaminationTeamRead>(`/api/v1/contamination-team/vault/${vaultId}/roster`)
  },

  async setPlace(
    vaultId: string,
    team: HazardTeam,
    dwellerId: string,
    active: boolean
  ): Promise<ContaminationTeamRead> {
    return apiPut<ContaminationTeamRead>(
      `/api/v1/contamination-team/vault/${vaultId}/${team}/${dwellerId}`,
      { active }
    )
  },
}
