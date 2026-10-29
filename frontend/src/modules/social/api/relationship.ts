import { api, apiGet, apiPost, apiPut } from '@/core/utils/api'
import type { CompatibilityScore, Relationship, RelationshipCreate } from '../models/relationship'

export interface VaultBreedingStats {
  relationships_updated: number
  conceptions: number
  births: number
  children_aged: number
}

export interface ProcessVaultBreedingResponse {
  stats: VaultBreedingStats
}

export const relationshipApi = {
  getByVault: (vaultId: string) => apiGet<Relationship[]>(`/api/v1/relationships/vault/${vaultId}`),

  get: (relationshipId: string) => apiGet<Relationship>(`/api/v1/relationships/${relationshipId}`),

  create: (data: RelationshipCreate) => apiPost<Relationship>('/api/v1/relationships/', data),

  initiateRomance: (relationshipId: string) =>
    apiPut<Relationship>(`/api/v1/relationships/${relationshipId}/romance`),

  makePartners: (relationshipId: string) =>
    apiPut<Relationship>(`/api/v1/relationships/${relationshipId}/partner`),

  marry: (relationshipId: string) =>
    apiPut<Relationship>(`/api/v1/relationships/${relationshipId}/marry`),

  breakUp: (relationshipId: string) =>
    api.delete<{ message: string }>(`/api/v1/relationships/${relationshipId}`),

  getCompatibility: (dweller1Id: string, dweller2Id: string) =>
    apiGet<CompatibilityScore>(`/api/v1/relationships/compatibility/${dweller1Id}/${dweller2Id}`),

  processVaultBreeding: (vaultId: string) =>
    apiPost<ProcessVaultBreedingResponse>(`/api/v1/relationships/vault/${vaultId}/process`),
}
