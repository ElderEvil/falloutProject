import type { components } from '@/core/types/api.generated'
import { apiGet, apiPost } from '@/core/utils/api'
import type { Objective, ObjectiveCreate } from '../models/objective'

export async function fetchObjectives(vaultId: string, skip: number, limit: number) {
  const data = await apiGet<components['schemas']['ObjectiveRead'][]>(
    `/api/v1/objectives/${vaultId}/`,
    { params: { skip, limit } }
  )
  return data.map((objective) => ({ ...objective, vault_id: vaultId }))
}

export async function addObjective(vaultId: string, objective: ObjectiveCreate) {
  await apiPost(`/api/v1/objectives/${vaultId}/`, objective)
}

export async function getObjective(vaultId: string, objectiveId: string) {
  return apiGet<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}`)
}

export async function claimObjective(vaultId: string, objectiveId: string) {
  return apiPost<Pick<Objective, 'progress' | 'total' | 'is_completed'>>(
    `/api/v1/objectives/${vaultId}/${objectiveId}/claim`
  )
}

export async function updateProgress(vaultId: string, objectiveId: string, progress: number) {
  return apiPost<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}/progress`, { progress })
}
