import { defineStore } from 'pinia'
import axios from '@/plugins/axios'
import type { DwellerFull, DwellerShort } from '@/types/dweller.types'

interface DwellerState {
  dwellers: DwellerShort[]
  detailedDwellers: Record<string, DwellerFull | null>
  loadingStates: Record<string, boolean>
  error: string | null
}

interface ApiResponse<T> {
  data: T
  message?: string
}

export const useDwellerStore = defineStore('dweller', {
  state: (): DwellerState => ({
    dwellers: [],
    detailedDwellers: {},
    loadingStates: {},
    error: null
  }),

  getters: {
    getDwellerById:
      (state) =>
      (id: string): DwellerShort | undefined =>
        state.dwellers.find((dweller) => dweller.id === id),

    getDetailedDweller:
      (state) =>
      (id: string): DwellerFull | null | undefined =>
        state.detailedDwellers[id],

    isLoading:
      (state) =>
      (id: string = 'all'): boolean =>
        !!state.loadingStates[id]
  },

  actions: {
    setLoading(id: string = 'all', loading: boolean) {
      this.loadingStates[id] = loading
    },

    setError(error: unknown) {
      this.error = error instanceof Error ? error.message : 'An unknown error occurred'
    },

    clearError() {
      this.error = null
    },

    async fetchDwellers(): Promise<boolean> {
      this.setLoading('all', true)
      this.clearError()

      try {
        const response = await axios.get<ApiResponse<DwellerShort[]>>('/api/v1/dwellers')
        this.dwellers = response.data.data
        return true
      } catch (error) {
        this.setError(error)
        return false
      } finally {
        this.setLoading('all', false)
      }
    },

    async fetchDwellerDetails(id: string): Promise<DwellerFull | null> {
      // Return cached data if available
      if (this.detailedDwellers[id]) {
        return this.detailedDwellers[id]
      }

      this.setLoading(id, true)
      this.clearError()

      try {
        const response = await axios.get<ApiResponse<DwellerFull>>(`/api/v1/dwellers/${id}`)
        this.detailedDwellers[id] = response.data.data
        return this.detailedDwellers[id]
      } catch (error) {
        this.setError(error)
        this.detailedDwellers[id] = null
        return null
      } finally {
        this.setLoading(id, false)
      }
    },

    async generateDwellerInfo(id: string): Promise<DwellerFull | null> {
      this.setLoading(id, true)
      this.clearError()

      try {
        const response = await axios.post<ApiResponse<DwellerFull>>(
          `/api/v1/dwellers/${id}/generate_with_ai`,
          null
        )

        const generatedDweller = response.data.data
        this.detailedDwellers[id] = generatedDweller

        // Update the dweller in the list if it exists
        const index = this.dwellers.findIndex((d) => d.id === id)
        if (index !== -1) {
          this.dwellers[index] = {
            ...this.dwellers[index],
            ...generatedDweller
          }
        }

        return generatedDweller
      } catch (error) {
        this.setError(error)
        return null
      } finally {
        this.setLoading(id, false)
      }
    },

    // Method to invalidate cached dweller details
    invalidateDwellerCache(id: string) {
      delete this.detailedDwellers[id]
    },

    // Method to update local dweller data
    updateDwellerLocal(id: string, data: Partial<DwellerFull>) {
      if (this.detailedDwellers[id]) {
        this.detailedDwellers[id] = {
          ...this.detailedDwellers[id]!,
          ...data
        }
      }

      const index = this.dwellers.findIndex((d) => d.id === id)
      if (index !== -1) {
        this.dwellers[index] = {
          ...this.dwellers[index],
          ...data
        }
      }
    }
  }
})
