import { defineStore, acceptHMRUpdate } from 'pinia'
import { ref } from 'vue'
import * as http from '@/core/plugins/httpClient'
import { handleStoreError } from '@/core/utils/errorHandler'
import type { Objective, ObjectiveCreate } from '../models/objective'

export const useObjectivesStore = defineStore('objectives', () => {
  // State
  const objectives = ref<Objective[]>([])

  // Actions
  async function fetchObjectives(vaultId: string, skip = 0, limit = 100): Promise<void> {
    try {
      objectives.value = await http.apiGet<Objective[]>(
        `/api/v1/objectives/${vaultId}/?skip=${skip}&limit=${limit}`,
        { _skipErrorNotification: true }
      )
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch objectives')
      throw error
    }
  }

  async function addObjective(vaultId: string, objectiveData: ObjectiveCreate): Promise<void> {
    try {
      await http.apiPost(`/api/v1/objectives/${vaultId}/`, objectiveData, {
        _skipErrorNotification: true,
      })
      await fetchObjectives(vaultId)
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to add objective')
      throw error
    }
  }

  async function getObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    try {
      return await http.apiGet<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}`, {
        _skipErrorNotification: true,
      })
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch objective')
      throw error
    }
  }

  async function completeObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    try {
      const updated = await http.apiPost<Objective>(
        `/api/v1/objectives/${vaultId}/${objectiveId}/complete`,
        undefined,
        { _skipErrorNotification: true }
      )
      const index = objectives.value.findIndex((obj) => obj.id === objectiveId)
      if (index !== -1) {
        objectives.value[index] = updated
      }
      return updated
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to complete objective')
      throw error
    }
  }

  async function updateProgress(
    vaultId: string,
    objectiveId: string,
    progress: number
  ): Promise<Objective> {
    try {
      const updated = await http.apiPost<Objective>(
        `/api/v1/objectives/${vaultId}/${objectiveId}/progress`,
        { progress },
        { _skipErrorNotification: true }
      )
      const index = objectives.value.findIndex((obj) => obj.id === objectiveId)
      if (index !== -1) {
        objectives.value[index] = updated
      }
      return updated
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to update objective progress')
      throw error
    }
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

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useObjectivesStore, import.meta.hot))
}
