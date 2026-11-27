import axios from '@/core/plugins/axios'
import type {
  CombatZoneLobbyRead,
  CombatZoneHistoryEntry,
  CombatZoneMatchRead,
  CombatZonePartyRead,
  CombatZoneStance,
} from '../models/combatZone'

const auth = (token: string) => ({ Authorization: `Bearer ${token}` })

export async function getLobby(token: string): Promise<CombatZoneLobbyRead> {
  const response = await axios.get<CombatZoneLobbyRead>('/api/v1/combat-zone/lobby', {
    headers: auth(token),
  })
  return response.data
}

export async function getParty(
  token: string,
  vaultId: string
): Promise<CombatZonePartyRead | null> {
  const response = await axios.get<CombatZonePartyRead | null>(
    `/api/v1/combat-zone/vault/${vaultId}/party`,
    { headers: auth(token) }
  )
  return response.data
}

export async function sendParty(
  token: string,
  vaultId: string,
  dwellerId: string
): Promise<CombatZonePartyRead> {
  const response = await axios.post<CombatZonePartyRead>(
    `/api/v1/combat-zone/vault/${vaultId}/party`,
    { dweller_id: dwellerId },
    { headers: auth(token) }
  )
  return response.data
}

export async function recallParty(token: string, vaultId: string): Promise<CombatZonePartyRead> {
  const response = await axios.delete<CombatZonePartyRead>(
    `/api/v1/combat-zone/vault/${vaultId}/party`,
    { headers: auth(token) }
  )
  return response.data
}

export async function setStance(
  token: string,
  vaultId: string,
  stance: CombatZoneStance
): Promise<CombatZonePartyRead> {
  const response = await axios.post<CombatZonePartyRead>(
    `/api/v1/combat-zone/vault/${vaultId}/stance`,
    { stance },
    { headers: auth(token) }
  )
  return response.data
}

export async function challenge(
  token: string,
  vaultId: string,
  targetPartyId: string
): Promise<CombatZoneMatchRead> {
  const response = await axios.post<CombatZoneMatchRead>(
    `/api/v1/combat-zone/vault/${vaultId}/challenge/${targetPartyId}`,
    undefined,
    { headers: auth(token) }
  )
  return response.data
}

export async function getMatch(token: string, matchId: string): Promise<CombatZoneMatchRead> {
  const response = await axios.get<CombatZoneMatchRead>(`/api/v1/combat-zone/matches/${matchId}`, {
    headers: auth(token),
  })
  return response.data
}

export async function getHistory(
  token: string,
  vaultId: string,
  limit = 20
): Promise<CombatZoneHistoryEntry[]> {
  const response = await axios.get<CombatZoneHistoryEntry[]>(
    `/api/v1/combat-zone/matches?vault_id=${vaultId}&limit=${limit}`,
    { headers: auth(token) }
  )
  return response.data
}
