import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/core/plugins/axios'
import type { Objective, ObjectiveCreate } from '../models/objective'

const DEBUG = import.meta.env.DEV

function debugLog(...args: unknown[]): void {
  if (DEBUG) {
    console.log('[Objectives DEBUG]', ...args)
  }
}

export const useObjectivesStore = defineStore('objectives', () => {
  // State
  const objectives = ref<Objective[]>([])

  // Actions
  async function fetchObjectives(vaultId: string, skip = 0, limit = 100): Promise<void> {
    try {
      debugLog(`Fetching objectives for vault ${vaultId}`, { skip, limit })
      const response = await axios.get<Objective[]>(`/api/v1/objectives/${vaultId}/`, {
        params: { skip, limit },
      })
      objectives.value = response.data
      debugLog(`Loaded ${response.data.length} objectives`, response.data)
    } catch (error: unknown) {
      console.error('Failed to fetch objectives:', error)
      throw error
    }
  }

  async function addObjective(vaultId: string, objectiveData: ObjectiveCreate): Promise<void> {
    try {
      debugLog(`Adding objective to vault ${vaultId}`, objectiveData)
      await axios.post(`/api/v1/objectives/${vaultId}/`, objectiveData)
      await fetchObjectives(vaultId)
      debugLog('Objective added successfully')
    } catch (error: unknown) {
      console.error('Failed to add objective:', error)
      throw error
    }
  }

  async function getObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    try {
      debugLog(`Fetching objective ${objectiveId} from vault ${vaultId}`)
      const response = await axios.get<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}`)
      debugLog('Objective fetched:', response.data)
      return response.data
    } catch (error: unknown) {
      console.error('Failed to fetch objective:', error)
      throw error
    }
  }

  async function completeObjective(vaultId: string, objectiveId: string): Promise<Objective> {
    try {
      debugLog(`Completing objective ${objectiveId} in vault ${vaultId}`)
      const response = await axios.post<Objective>(`/api/v1/objectives/${vaultId}/${objectiveId}/complete`)
      debugLog('Objective completed:', response.data)
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
      debugLog(`Updating progress for objective ${objectiveId} in vault ${vaultId}`, { progress })
      const response = await axios.post<Objective>(
        `/api/v1/objectives/${vaultId}/${objectiveId}/progress`,
        { progress },
      )
      debugLog('Progress updated:', response.data)
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
