import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/core/plugins/axios'
import type { Objective, ObjectiveCreate } from '../models/objective'

export const useObjectivesStore = defineStore('objectives', () => {
  // State
  const objectives = ref<Objective[]>([])

  // Actions
  async function fetchObjectives(vaultId: string, skip = 0, limit = 100): Promise<void> {
    const response = await axios.get<Objective[]>(`/api/v1/objectives/${vaultId}/`, {
      params: { skip, limit },
    })
    objectives.value = response.data
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
    const response = await axios.post<Objective>(
      `/api/v1/objectives/${vaultId}/${objectiveId}/complete`
    )
    const index = objectives.value.findIndex((obj) => obj.id === objectiveId)
    if (index !== -1) {
      objectives.value[index] = response.data
    }
    return response.data
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
    fetchObjectives,
    addObjective,
    getObjective,
    completeObjective,
    updateProgress,
  }
})
