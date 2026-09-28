import axios from '@/core/plugins/axios'
import type { ContaminationTeamRead, HazardTeam } from '../models/contaminationTeam'

export const contaminationTeamApi = {
  async getRoster(vaultId: string, token: string): Promise<ContaminationTeamRead> {
    const response = await axios.get<ContaminationTeamRead>(
      `/api/v1/contamination-team/vault/${vaultId}/roster`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    return response.data
  },

  async setPlace(
    vaultId: string,
    team: HazardTeam,
    dwellerId: string,
    active: boolean,
    token: string
  ): Promise<ContaminationTeamRead> {
    const response = await axios.put<ContaminationTeamRead>(
      `/api/v1/contamination-team/vault/${vaultId}/${team}/${dwellerId}`,
      { active },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    return response.data
  },
}