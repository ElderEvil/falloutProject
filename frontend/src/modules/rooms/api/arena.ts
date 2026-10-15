import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

type ArenaState = components['schemas']['ArenaState']
type ArenaRoomState = components['schemas']['ArenaRoomState']
type ArenaRosterEntry = components['schemas']['ArenaRosterEntry']
type ArenaFighter = components['schemas']['ArenaFighter']
type ArenaMode = components['schemas']['ArenaMode']
type ArenaCreature = components['schemas']['ArenaCreature']

export type { ArenaCreature, ArenaFighter, ArenaRosterEntry, ArenaRoomState, ArenaState, ArenaMode }

export interface ArenaFighterSelection {
  mode: ArenaMode
  fighterAId: string | null
  fighterBId: string | null
  fighterCId?: string | null
  fighterDId?: string | null
  opponentKeys?: string[]
  teamABotKey?: string | null
  teamBBotKey?: string | null
}

export const arenaApi = {
  async fetchState(vaultId: string, token: string): Promise<ArenaState> {
    const response = await axios.get<ArenaState>(`/api/v1/arena/vault/${vaultId}/state`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return response.data
  },

  async fetchCreatures(vaultId: string, token: string): Promise<ArenaCreature[]> {
    const response = await axios.get<ArenaCreature[]>(`/api/v1/arena/vault/${vaultId}/creatures`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return response.data
  },

  async setFighters(
    vaultId: string,
    roomId: string,
    selection: ArenaFighterSelection,
    token: string
  ): Promise<void> {
    await axios.post(
      `/api/v1/arena/vault/${vaultId}/rooms/${roomId}/fighters`,
      {
        mode: selection.mode,
        fighter_a_id: selection.fighterAId,
        fighter_b_id: selection.fighterBId,
        fighter_c_id: selection.fighterCId ?? null,
        fighter_d_id: selection.fighterDId ?? null,
        opponent_keys: selection.opponentKeys ?? [],
        team_a_bot_key: selection.teamABotKey ?? null,
        team_b_bot_key: selection.teamBBotKey ?? null,
      },
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
