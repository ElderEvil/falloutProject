import { contaminationTeamApi } from '@/modules/contamination-team/api/roster'
import type {
  ContaminationTeamRead,
  HazardTeam,
} from '@/modules/contamination-team/models/contaminationTeam'

export function fetchResponseRoster(
  vaultId: string,
  token: string
): Promise<ContaminationTeamRead> {
  return contaminationTeamApi.getRoster(vaultId, token)
}

export function updateResponseTeamPlace(
  vaultId: string,
  team: HazardTeam,
  dwellerId: string,
  active: boolean,
  token: string
): Promise<ContaminationTeamRead> {
  return contaminationTeamApi.setPlace(vaultId, team, dwellerId, active, token)
}
