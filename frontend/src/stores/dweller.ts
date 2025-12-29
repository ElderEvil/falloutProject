import { defineStore } from 'pinia'
import axios from '@/plugins/axios'
import type { Dweller, DwellerShort } from '@/models/dweller'

export const useDwellerStore = defineStore('dweller', {
  state: () => ({
    dwellers: [] as DwellerShort[],
    detailedDwellers: {} as Record<string, Dweller | null>
  }),
  actions: {
    async fetchDwellers(token: string) {
      try {
        const response = await axios.get('/api/v1/dwellers', {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.dwellers = response.data
      } catch (error) {
        console.error('Failed to fetch dwellers', error)
      }
    },
    async fetchDwellersByVault(vaultId: string, token: string) {
      try {
        const response = await axios.get(`/api/v1/dwellers/vault/${vaultId}/`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.dwellers = response.data
      } catch (error) {
        console.error(`Failed to fetch dwellers for vault ${vaultId}`, error)
      }
    },
    async fetchDwellerDetails(id: string, token: string, forceRefresh = false) {
      if (this.detailedDwellers[id] && !forceRefresh) return this.detailedDwellers[id]
      try {
        const response = await axios.get(`/api/v1/dwellers/${id}`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.detailedDwellers[id] = response.data
        return this.detailedDwellers[id]
      } catch (error) {
        console.error(`Failed to fetch details for dweller ${id}`, error)
        return null
      }
    },
    async generateDwellerInfo(id: string, token: string) {
      try {
        const response = await axios.post(`/api/v1/dwellers/${id}/generate_with_ai/`, null, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })
        this.detailedDwellers[id] = response.data
        return this.detailedDwellers[id]
      } catch (error) {
        console.error(`Failed to generate image for dweller ${id}`, error)
        return null
      }
    },
    async assignDwellerToRoom(dwellerId: string, roomId: string, token: string) {
      try {
        const response = await axios.post(
          `/api/v1/dwellers/${dwellerId}/move_to/${roomId}`,
          null,
          {
            headers: {
              Authorization: `Bearer ${token}`
            }
          }
        )

        // Update the dweller in the list
        const dwellerIndex = this.dwellers.findIndex(d => d.id === dwellerId)
        if (dwellerIndex !== -1) {
          this.dwellers[dwellerIndex] = { ...this.dwellers[dwellerIndex], room_id: roomId }
        }

        // Update detailed dweller if cached
        if (this.detailedDwellers[dwellerId]) {
          this.detailedDwellers[dwellerId] = response.data
        }

        return response.data
      } catch (error) {
        console.error(`Failed to assign dweller ${dwellerId} to room ${roomId}`, error)
        throw error
      }
    },
    async unassignDwellerFromRoom(dwellerId: string, token: string) {
      try {
        // Move dweller to null room (unassign)
        const response = await axios.put(
          `/api/v1/dwellers/${dwellerId}`,
          { room_id: null },
          {
            headers: {
              Authorization: `Bearer ${token}`
            }
          }
        )

        // Update the dweller in the list
        const dwellerIndex = this.dwellers.findIndex(d => d.id === dwellerId)
        if (dwellerIndex !== -1) {
          this.dwellers[dwellerIndex] = { ...this.dwellers[dwellerIndex], room_id: null }
        }

        // Update detailed dweller if cached
        if (this.detailedDwellers[dwellerId]) {
          this.detailedDwellers[dwellerId] = response.data
        }

        return response.data
      } catch (error) {
        console.error(`Failed to unassign dweller ${dwellerId}`, error)
        throw error
      }
    }
  }
})
