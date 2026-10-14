import axios from '@/core/plugins/axios'
import { contaminationTeamApi } from '@/modules/contamination-team/api/roster'
import type {
  ContaminationTeamRead,
  HazardTeam,
} from '@/modules/contamination-team/models/contaminationTeam'
import type { Room } from '../models/room'

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

export async function expandResponseStation(roomId: string, token: string): Promise<Room> {
  const response = await axios.post<Room>(
    `/api/v1/rooms/expand/${roomId}`,
    {},
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}
