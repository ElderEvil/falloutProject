import axios from '@/core/plugins/axios'

export interface ArenaFighter {
  id: string
  name: string
  level: number
  health: number
  max_health: number
  power: number
}

export interface ArenaRosterEntry {
  id: string
  name: string
  level: number
  health: number
  max_health: number
}

export interface ArenaMatchEvent {
  id: string
  round_seq: number
  kind: 'hit' | 'finish' | 'reward'
  message: string
}

export interface ArenaRoomState {
  room_id: string
  room_name: string
  tier: number
  fighter_a_id: string | null
  fighter_b_id: string | null
  fighters: ArenaFighter[]
  roster: ArenaRosterEntry[]
  fight_ready: boolean
  match_done: boolean
  fight_started: boolean
  countdown_remaining: number
  can_start: boolean
  events: ArenaMatchEvent[]
}

export interface ArenaState {
  rooms: ArenaRoomState[]
}

export async function fetchArenaState(vaultId: string, token: string): Promise<ArenaState> {
  const response = await axios.get<ArenaState>(`/api/v1/arena/vault/${vaultId}/state`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.data
}

export async function setArenaFighters(
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
}

export async function startArenaFight(vaultId: string, roomId: string, token: string): Promise<void> {
  await axios.post(`/api/v1/arena/vault/${vaultId}/rooms/${roomId}/start`, null, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export async function clearArenaEvents(vaultId: string, roomId: string, token: string): Promise<number> {
  const response = await axios.delete<{ cleared: number }>(
    `/api/v1/arena/vault/${vaultId}/rooms/${roomId}/events`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data.cleared
}
