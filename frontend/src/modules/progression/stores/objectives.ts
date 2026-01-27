import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/core/plugins/axios'
import type { Objective, ObjectiveCreate } from '../models/objective'

export const useObjectivesStore = defineStore('objectives', () => {
  // State
  const objectives = ref<Objective[]>([])

  // Actions
  async function fetchObjectives(vaultId: string, skip = 0, limit = 100): Promise<void> {
    try {
      const response = await axios.get<Objective[]>(`/api/v1/objectives/${vaultId}/`, {
        params: { skip, limit },
      })
      objectives.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch objectives:', error)
      throw error
    }
  }

  async function addObjective(vaultId: string, objectiveData: ObjectiveCreate): Promise<void> {
    try {
      await axios.post(`/api/v1/objectives/${vaultId}/`, objectiveData)
      await fetchObjectives(vaultId) // Refresh the objectives list after adding a new one
    } catch (error: unknown) {
      console.error('Failed to add objective:', error)
      throw error
    }
  }

  async function getObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    try {
      const response = await axios.get<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}`)
      return response.data
    } catch (error: unknown) {
      console.error('Failed to fetch objective:', error)
      throw error
    }
  }

  return {
    objectives,
    fetchObjectives,
    addObjective,
    getObjective,
  }
})
