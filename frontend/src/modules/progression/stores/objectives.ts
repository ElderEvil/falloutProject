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
      await fetchObjectives(vaultId)
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

  async function completeObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    try {
      const response = await axios.post<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}/complete`)
      const index = objectives.value.findIndex((obj) => obj.id === objectiveId)
      if (index !== -1) {
        objectives.value[index] = response.data
      }
      return response.data
    } catch (error: unknown) {
      console.error('Failed to complete objective:', error)
      throw error
    }
  }

  async function updateProgress(
    vaultId: string,
    objectiveId: string,
    progress: number,
  ): Promise<Objective> {
    try {
      const response = await axios.post<Objective>(
        `/api/v1/objectives/${vaultId}/${objectiveId}/progress`,
        { progress },
      )
      const index = objectives.value.findIndex((obj) => obj.id === objectiveId)
      if (index !== -1) {
        objectives.value[index] = response.data
      }
      return response.data
    } catch (error: unknown) {
      console.error('Failed to update objective progress:', error)
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
