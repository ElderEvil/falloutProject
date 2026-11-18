import type { components } from '@/core/types/api.generated'
import { api, apiGet, apiPost } from '@/core/utils/api'

type VaultReadWithNumbers = components['schemas']['VaultReadWithNumbers']
type VaultScenarioRead = components['schemas']['VaultScenarioRead']
export type VaultMode = components['schemas']['VaultModeEnum']

/** Game state is not yet in the generated API schemas. */
export interface GameState {
  is_paused: boolean
  paused_at?: string | null
  resumed_at?: string | null
  total_game_time?: number
}

export function getVaults(): Promise<VaultReadWithNumbers[]> {
  return apiGet<VaultReadWithNumbers[]>('/api/v1/vaults/my')
}

export function getScenarioOptions(): Promise<VaultScenarioRead[]> {
  return apiGet<VaultScenarioRead[]>('/api/v1/vaults/scenarios')
}

export function createVault(payload: {
  number: number
  boosted: boolean
  vault_mode: VaultMode
  scenario?: string
}): Promise<{ id: string }> {
  return apiPost<{ id: string }>('/api/v1/vaults/initiate', payload)
}

export function deleteVault(id: string, hardDelete: boolean): Promise<unknown> {
  return api.delete(`/api/v1/vaults/${id}`, hardDelete ? { params: { hard_delete: true } } : {})
}

export function getVault(id: string): Promise<VaultReadWithNumbers> {
  return apiGet<VaultReadWithNumbers>(`/api/v1/vaults/${id}`)
}

export function getGameState(vaultId: string): Promise<GameState> {
  return apiGet<GameState>(`/api/v1/game/vaults/${vaultId}/game-state`)
}

export function pauseVault(vaultId: string): Promise<GameState> {
  return apiPost<GameState>(`/api/v1/game/vaults/${vaultId}/pause`, {})
}

export function resumeVault(vaultId: string): Promise<GameState> {
  return apiPost<GameState>(`/api/v1/game/vaults/${vaultId}/resume`, {})
}

export function pingPresence(vaultId: string): Promise<unknown> {
  return apiPost(`/api/v1/game/vaults/${vaultId}/presence`, {})
}
