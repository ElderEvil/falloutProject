import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/core/plugins/axios'
import type { Objective, ObjectiveCreate } from '../models/objective'

export const useObjectivesStore = defineStore('objectives', () => {
  // State
  const objectives = ref<Objective[]>([])
  const objectivesVaultId = ref<string | null>(null)
  let fetchGeneration = 0

  // Actions
  async function fetchObjectives(vaultId: string, skip = 0, limit = 100): Promise<void> {
    const generation = ++fetchGeneration
    if (objectivesVaultId.value !== vaultId) objectives.value = []
    objectivesVaultId.value = vaultId
    const response = await axios.get<Objective[]>(`/api/v1/objectives/${vaultId}/`, {
      params: { skip, limit },
    })
    if (generation === fetchGeneration) objectives.value = response.data
  }

  async function addObjective(vaultId: string, objectiveData: ObjectiveCreate): Promise<void> {
    await axios.post(`/api/v1/objectives/${vaultId}/`, objectiveData)
    await fetchObjectives(vaultId)
  }

  async function getObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    const response = await axios.get<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}`)
    return response.data
  }

  async function completeObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    const objective = objectives.value.find((item) => item.id === objectiveId)
    if (!objective) throw new Error('Objective no longer available')
    ++fetchGeneration
    const response = await axios.post<Pick<Objective, 'progress' | 'total' | 'is_completed'>>(
      `/api/v1/objectives/${vaultId}/${objectiveId}/claim`
    )
    const completed = { ...objective, ...response.data }
    if (objectivesVaultId.value === vaultId) {
      ++fetchGeneration
      const index = objectives.value.findIndex((item) => item.id === objectiveId)
      if (index !== -1) objectives.value[index] = completed
    }
    return completed
  }

  async function updateProgress(
    vaultId: string,
    objectiveId: string,
    progress: number
  ): Promise<Objective> {
    const response = await axios.post<Objective>(
      `/api/v1/objectives/${vaultId}/${objectiveId}/progress`,
      { progress }
    )
    const index = objectives.value.findIndex((obj) => obj.id === objectiveId)
    if (index !== -1) {
      objectives.value[index] = response.data
    }
    return response.data
  }

  return {
    objectives,
    objectivesVaultId,
    fetchObjectives,
    addObjective,
    getObjective,
    completeObjective,
    updateProgress,
  }
})
