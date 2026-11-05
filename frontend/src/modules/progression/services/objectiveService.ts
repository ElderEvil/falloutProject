import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'
import type { Objective, ObjectiveCreate } from '../models/objective'

export async function fetchObjectives(vaultId: string, skip: number, limit: number) {
  const { data } = await axios.get<components['schemas']['ObjectiveRead'][]>(
    `/api/v1/objectives/${vaultId}/`,
    {
      params: { skip, limit },
    }
  )
  return data.map((objective) => ({ ...objective, vault_id: vaultId }))
}

export async function addObjective(vaultId: string, objective: ObjectiveCreate) {
  await axios.post(`/api/v1/objectives/${vaultId}/`, objective)
}

export async function getObjective(vaultId: string, objectiveId: string) {
  const { data } = await axios.get<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}`)
  return data
}

export async function claimObjective(vaultId: string, objectiveId: string) {
  const { data } = await axios.post<Pick<Objective, 'progress' | 'total' | 'is_completed'>>(
    `/api/v1/objectives/${vaultId}/${objectiveId}/claim`
  )
  return data
}

export async function updateProgress(vaultId: string, objectiveId: string, progress: number) {
  const { data } = await axios.post<Objective>(
    `/api/v1/objectives/${vaultId}/${objectiveId}/progress`,
    { progress }
  )
  return data
}
