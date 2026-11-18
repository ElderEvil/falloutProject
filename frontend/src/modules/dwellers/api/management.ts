import { api, apiPost, apiPut } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'
import type { Dweller } from '../models/dweller'

type AutoAssignResponse = components['schemas']['AutoAssignResponse']
type DwellerWithRoom = Dweller & { room_id: string | null }

export function moveToRoom(dwellerId: string, roomId: string): Promise<DwellerWithRoom> {
  return apiPost<DwellerWithRoom>(`/api/v1/dwellers/${dwellerId}/move_to/${roomId}`)
}

export function softDelete(dwellerId: string): Promise<Dweller> {
  return apiPost<Dweller>(`/api/v1/dwellers/${dwellerId}/soft-delete`)
}

export function updateDweller(
  dwellerId: string,
  payload: Record<string, unknown>
): Promise<DwellerWithRoom> {
  return apiPut<DwellerWithRoom>(`/api/v1/dwellers/${dwellerId}`, payload)
}

export function autoAssign(dwellerId: string): Promise<DwellerWithRoom> {
  return apiPost<DwellerWithRoom>(`/api/v1/dwellers/${dwellerId}/auto_assign`)
}

export function rename(
  dwellerId: string,
  payload: { first_name: string; last_name?: string | null }
): Promise<Dweller> {
  return api.patch<Dweller>(`/api/v1/dwellers/${dwellerId}/rename`, payload)
}

export function unassignAll(vaultId: string): Promise<{ unassigned_count: number }> {
  return apiPost<{ unassigned_count: number }>(`/api/v1/vaults/${vaultId}/dwellers/unassign-all`)
}

export type VaultAutoAssignEndpoint =
  | 'auto-assign-production'
  | 'auto-assign-training'
  | 'auto-assign-all'
  | 'auto-assign-crafting'

export function autoAssignVault(
  endpoint: VaultAutoAssignEndpoint,
  vaultId: string,
  ageGroup?: string
): Promise<AutoAssignResponse> {
  const query = ageGroup ? `?age_group=${ageGroup}` : ''
  return apiPost<AutoAssignResponse>(`/api/v1/vaults/${vaultId}/dwellers/${endpoint}${query}`, null)
}
