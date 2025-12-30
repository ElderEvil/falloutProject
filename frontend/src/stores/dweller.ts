import { defineStore } from 'pinia'
import axios from '@/plugins/axios'
import type { Dweller, DwellerShort } from '@/models/dweller'
import { useExplorationStore } from './exploration'

export type DwellerStatus = 'idle' | 'working' | 'exploring' | 'unknown'

export interface DwellerWithStatus extends DwellerShort {
  status: DwellerStatus
}

export type DwellerSortBy = 'name' | 'level' | 'strength' | 'perception' | 'endurance' | 'charisma' | 'intelligence' | 'agility' | 'luck'
export type SortDirection = 'asc' | 'desc'

export const useDwellerStore = defineStore('dweller', {
  state: () => ({
    dwellers: [] as DwellerShort[],
    detailedDwellers: {} as Record<string, Dweller | null>,
    // Filter and sort state
    filterStatus: 'all' as DwellerStatus | 'all',
    sortBy: 'name' as DwellerSortBy,
    sortDirection: 'asc' as SortDirection
  }),
  getters: {
    /**
     * Get dweller status based on their current assignment
     */
    getDwellerStatus: (state) => {
      return (dwellerId: string): DwellerStatus => {
        const explorationStore = useExplorationStore()
        const dweller = state.dwellers.find(d => d.id === dwellerId)

        if (!dweller) return 'unknown'

        // Check if exploring
        if (explorationStore.isDwellerExploring(dwellerId)) {
          return 'exploring'
        }

        // Check if working (assigned to a room)
        if (dweller.room_id) {
          return 'working'
        }

        // Otherwise idle
        return 'idle'
      }
    },

    /**
     * Get all dwellers with their computed status
     */
    dwellersWithStatus(): DwellerWithStatus[] {
      const explorationStore = useExplorationStore()
      return this.dwellers.map(dweller => ({
        ...dweller,
        status: this.getDwellerStatus(dweller.id)
      }))
    },

    /**
     * Get dwellers filtered by status
     */
    getDwellersByStatus: (state) => {
      return (status: DwellerStatus): DwellerWithStatus[] => {
        const explorationStore = useExplorationStore()
        return state.dwellers
          .filter(dweller => {
            const dwellerStatus = explorationStore.isDwellerExploring(dweller.id)
              ? 'exploring'
              : dweller.room_id
                ? 'working'
                : 'idle'
            return dwellerStatus === status
          })
          .map(dweller => ({
            ...dweller,
            status
          }))
      }
    },

    /**
     * Get filtered and sorted dwellers based on current filter/sort settings
     */
    filteredAndSortedDwellers(): DwellerWithStatus[] {
      let result = this.dwellersWithStatus

      // Apply status filter
      if (this.filterStatus !== 'all') {
        result = result.filter(dweller => dweller.status === this.filterStatus)
      }

      // Apply sorting
      result = [...result].sort((a, b) => {
        let comparison = 0

        if (this.sortBy === 'name') {
          const nameA = `${a.first_name} ${a.last_name}`.toLowerCase()
          const nameB = `${b.first_name} ${b.last_name}`.toLowerCase()
          comparison = nameA.localeCompare(nameB)
        } else if (this.sortBy === 'level') {
          comparison = a.level - b.level
        } else {
          // SPECIAL stats sorting
          comparison = a[this.sortBy] - b[this.sortBy]
        }

        return this.sortDirection === 'asc' ? comparison : -comparison
      })

      return result
    }
  },
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
    },
    setFilterStatus(status: DwellerStatus | 'all') {
      this.filterStatus = status
      // Persist to localStorage
      localStorage.setItem('dwellerFilterStatus', status)
    },
    setSortBy(sortBy: DwellerSortBy) {
      this.sortBy = sortBy
      // Persist to localStorage
      localStorage.setItem('dwellerSortBy', sortBy)
    },
    setSortDirection(direction: SortDirection) {
      this.sortDirection = direction
      // Persist to localStorage
      localStorage.setItem('dwellerSortDirection', direction)
    },
    loadFilterPreferences() {
      // Load from localStorage
      const savedFilterStatus = localStorage.getItem('dwellerFilterStatus') as DwellerStatus | 'all' | null
      const savedSortBy = localStorage.getItem('dwellerSortBy') as DwellerSortBy | null
      const savedSortDirection = localStorage.getItem('dwellerSortDirection') as SortDirection | null

      if (savedFilterStatus) this.filterStatus = savedFilterStatus
      if (savedSortBy) this.sortBy = savedSortBy
      if (savedSortDirection) this.sortDirection = savedSortDirection
    }
  }
})
