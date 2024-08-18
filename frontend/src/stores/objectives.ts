import { defineStore } from 'pinia'
import axios from '@/plugins/axios'

export const useObjectivesStore = defineStore('objectives', {
  state: () => ({
    objectives: [] as Array<any>
  }),
  actions: {
    async fetchObjectives(vaultId: string, skip = 0, limit = 100) {
      try {
        const response = await axios.get(`/api/v1/objectives/${vaultId}/`, {
          params: { skip, limit }
        })
        this.objectives = response.data
      } catch (error) {
        console.error('Failed to fetch objectives:', error)
        throw error
      }
    },
    async addObjective(vaultId: string, objectiveData: any) {
      try {
        await axios.post(`/api/v1/${vaultId}/`, objectiveData)
        await this.fetchObjectives(vaultId) // Refresh the objectives list after adding a new one
      } catch (error) {
        console.error('Failed to add objective:', error)
        throw error
      }
    },
    async getObjective(vaultId: string, objectiveId: string) {
      try {
        const response = await axios.get(`/api/v1/${vaultId}/${objectiveId}`)
        return response.data
      } catch (error) {
        console.error('Failed to fetch objective:', error)
        throw error
      }
    }
  }
})
