import { api, apiGet, apiPost } from '@/core/utils/api'
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

const selectionPayload = (selection: ArenaFighterSelection) => ({
  mode: selection.mode,
  fighter_a_id: selection.fighterAId,
  fighter_b_id: selection.fighterBId,
  fighter_c_id: selection.fighterCId ?? null,
  fighter_d_id: selection.fighterDId ?? null,
  opponent_keys: selection.opponentKeys ?? [],
  team_a_bot_key: selection.teamABotKey ?? null,
  team_b_bot_key: selection.teamBBotKey ?? null,
})

export const arenaApi = {
  fetchState: (vaultId: string) => apiGet<ArenaState>(`/api/v1/arena/vault/${vaultId}/state`),

  fetchCreatures: (vaultId: string) =>
    apiGet<ArenaCreature[]>(`/api/v1/arena/vault/${vaultId}/creatures`),

  setFighters: (vaultId: string, roomId: string, selection: ArenaFighterSelection) =>
    apiPost<void>(
      `/api/v1/arena/vault/${vaultId}/rooms/${roomId}/fighters`,
      selectionPayload(selection)
    ),

  startFight: (vaultId: string, roomId: string, selection?: ArenaFighterSelection) =>
    apiPost<void>(
      `/api/v1/arena/vault/${vaultId}/rooms/${roomId}/start`,
      selection ? selectionPayload(selection) : null
    ),

  stopFight: (vaultId: string, roomId: string) =>
    apiPost<void>(`/api/v1/arena/vault/${vaultId}/rooms/${roomId}/stop`, null),

  queueSkill: (vaultId: string, roomId: string, fighterId: string) =>
    apiPost<void>(`/api/v1/arena/vault/${vaultId}/rooms/${roomId}/skill`, {
      fighter_id: fighterId,
    }),

  clearEvents: async (vaultId: string, roomId: string): Promise<number> => {
    const response = await api.delete<{ cleared: number }>(
      `/api/v1/arena/vault/${vaultId}/rooms/${roomId}/events`
    )
    return response.cleared
  },
}
