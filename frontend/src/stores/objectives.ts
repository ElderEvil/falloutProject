// src/stores/objectives.ts
import { defineStore } from 'pinia'
import axios from 'axios'

const API_URL = 'api/v1/objectives'

export const useObjectivesStore = defineStore('objectives', {
  state: () => ({
    objectives: [] as Array<any>
  }),
  actions: {
    async fetchObjectives(vaultId: string, skip = 0, limit = 100) {
      try {
        const response = await axios.get(`${API_URL}/${vaultId}/`, {
          params: { skip, limit }
        })
        this.objectives = response.data
      } catch (error) {
        console.error('Failed to fetch objectives:', error)
        throw error
      }
    },
    async completeObjective(vaultId: string, objectiveId: string) {
      try {
        await axios.post(`${API_URL}/${vaultId}/${objectiveId}/complete`)
        await this.fetchObjectives(vaultId) // Refresh the objectives list after completion
      } catch (error) {
        console.error('Failed to complete objective:', error)
        throw error
      }
    },
    async addObjective(vaultId: string, objectiveData: any) {
      try {
        await axios.post(`${API_URL}/${vaultId}/`, objectiveData)
        await this.fetchObjectives(vaultId) // Refresh the objectives list after adding a new one
      } catch (error) {
        console.error('Failed to add objective:', error)
        throw error
      }
    },
    async getObjective(vaultId: string, objectiveId: string) {
      try {
        const response = await axios.get(`${API_URL}/${vaultId}/${objectiveId}`)
        return response.data
      } catch (error) {
        console.error('Failed to fetch objective:', error)
        throw error
      }
    }
  }
})
