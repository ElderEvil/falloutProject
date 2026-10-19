import axios from '@/core/plugins/axios'
import type {
  CombatZoneLobbyRead,
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

export async function setVaultEnabled(
  token: string,
  vaultId: string,
  enabled: boolean
): Promise<{ vault_id: string; enabled: boolean }> {
  const response = await axios.post<{ vault_id: string; enabled: boolean }>(
    `/api/v1/combat-zone/admin/vault/${vaultId}/enabled`,
    { enabled },
    { headers: auth(token) }
  )
  return response.data
}
