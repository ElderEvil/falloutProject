import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

type ArenaState = components['schemas']['ArenaState']
type ArenaRoomState = components['schemas']['ArenaRoomState']
type ArenaRosterEntry = components['schemas']['ArenaRosterEntry']
type ArenaFighter = components['schemas']['ArenaFighter']

export type { ArenaFighter, ArenaRosterEntry, ArenaRoomState, ArenaState }

export const arenaApi = {
  async fetchState(vaultId: string, token: string): Promise<ArenaState> {
    const response = await axios.get<ArenaState>(`/api/v1/arena/vault/${vaultId}/state`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return response.data
  },

  async setFighters(
    vaultId: string,
    roomId: string,
    fighterAId: string | null,
    fighterBId: string | null,
    token: string
  ): Promise<void> {
    await axios.post(
      `/api/v1/arena/vault/${vaultId}/rooms/${roomId}/fighters`,
      { fighter_a_id: fighterAId, fighter_b_id: fighterBId },
      { headers: { Authorization: `Bearer ${token}` } }
    )
  },

  async startFight(vaultId: string, roomId: string, token: string): Promise<void> {
    await axios.post(`/api/v1/arena/vault/${vaultId}/rooms/${roomId}/start`, null, {
      headers: { Authorization: `Bearer ${token}` },
    })
  },

  async clearEvents(vaultId: string, roomId: string, token: string): Promise<number> {
    const response = await axios.delete<{ cleared: number }>(
      `/api/v1/arena/vault/${vaultId}/rooms/${roomId}/events`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    return response.data.cleared
  },
}
