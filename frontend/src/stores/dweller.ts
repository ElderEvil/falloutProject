import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import axios from '@/plugins/axios'
import type { Dweller, DwellerShort } from '@/models/dweller'
import { useToast } from '@/composables/useToast'

export type DwellerStatus = 'idle' | 'working' | 'exploring' | 'training' | 'resting' | 'dead' | 'unknown'

export interface DwellerWithStatus extends DwellerShort {
  status: DwellerStatus
}

export type DwellerSortBy = 'name' | 'level' | 'strength' | 'perception' | 'endurance' | 'charisma' | 'intelligence' | 'agility' | 'luck'
export type SortDirection = 'asc' | 'desc'

export const useDwellerStore = defineStore('dweller', () => {
  const toast = useToast()

  // State
  const dwellers = ref<DwellerShort[]>([])
  const detailedDwellers = ref<Record<string, Dweller | null>>({})
  const isLoading = ref(false)

  // Filter and sort state (persisted in localStorage)
  const filterStatus = useLocalStorage<DwellerStatus | 'all'>('dwellerFilterStatus', 'all')
  const sortBy = useLocalStorage<DwellerSortBy>('dwellerSortBy', 'name')
  const sortDirection = useLocalStorage<SortDirection>('dwellerSortDirection', 'asc')
  const viewMode = useLocalStorage<'list' | 'grid'>('dwellerViewMode', 'list')

  /**
   * Get dweller status - now directly from backend
   */
  const getDwellerStatus = computed(() => {
    return (dwellerId: string): DwellerStatus => {
      const dweller = dwellers.value.find((d) => d.id === dwellerId)
      if (!dweller) return 'unknown'

      // Backend now provides status directly
      return (dweller.status as DwellerStatus) || 'unknown'
    }
  })

  /**
   * Get all dwellers with their status (already provided by backend)
   */
  const dwellersWithStatus = computed((): DwellerWithStatus[] => {
    return dwellers.value.map((dweller) => ({
      ...dweller,
      status: (dweller.status as DwellerStatus) || 'unknown'
    }))
  })

  /**
   * Get dwellers filtered by status - filters are now applied on backend
   */
  const getDwellersByStatus = computed(() => {
    return (status: DwellerStatus): DwellerWithStatus[] => {
      return dwellers.value
        .filter((dweller) => dweller.status === status)
        .map((dweller) => ({
          ...dweller,
          status: (dweller.status as DwellerStatus) || 'unknown'
        }))
    }
  })

  /**
   * Get filtered and sorted dwellers based on current filter/sort settings
   */
  const filteredAndSortedDwellers = computed((): DwellerWithStatus[] => {
    let result = dwellersWithStatus.value

    // Apply status filter
    if (filterStatus.value !== 'all') {
      result = result.filter((dweller) => dweller.status === filterStatus.value)
    }

    // Apply sorting
    result = [...result].sort((a, b) => {
      let comparison = 0

      if (sortBy.value === 'name') {
        const nameA = `${a.first_name} ${a.last_name}`.toLowerCase()
        const nameB = `${b.first_name} ${b.last_name}`.toLowerCase()
        comparison = nameA.localeCompare(nameB)
      } else if (sortBy.value === 'level') {
        comparison = a.level - b.level
      } else {
        // SPECIAL stats sorting
        comparison = a[sortBy.value] - b[sortBy.value]
      }

      return sortDirection.value === 'asc' ? comparison : -comparison
    })

    return result
  })

  // Actions
  async function fetchDwellers(token: string): Promise<void> {
    try {
      const response = await axios.get('/api/v1/dwellers', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
      dwellers.value = response.data
    } catch (error) {
      console.error('Failed to fetch dwellers', error)
    }
  }

  async function fetchDwellersByVault(
    vaultId: string,
    token: string,
    options?: {
      status?: DwellerStatus
      search?: string
      sortBy?: string
      order?: 'asc' | 'desc'
      skip?: number
      limit?: number
    }
  ): Promise<void> {
    isLoading.value = true
    try {
      const params = new URLSearchParams()
      if (options?.status && options.status !== 'all') params.append('status', options.status)
      if (options?.search) params.append('search', options.search)
      if (options?.sortBy) params.append('sort_by', options.sortBy)
      if (options?.order) params.append('order', options.order)
      if (options?.skip !== undefined) params.append('skip', options.skip.toString())
      if (options?.limit !== undefined) params.append('limit', options.limit.toString())

      const queryString = params.toString()
      const url = `/api/v1/dwellers/vault/${vaultId}/${queryString ? `?${queryString}` : ''}`

      const response = await axios.get(url, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
      dwellers.value = response.data
    } catch (error) {
      console.error(`Failed to fetch dwellers for vault ${vaultId}`, error)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchDwellerDetails(
    id: string,
    token: string,
    forceRefresh = false
  ): Promise<Dweller | null> {
    if (detailedDwellers.value[id] && !forceRefresh) return detailedDwellers.value[id]
    try {
      const response = await axios.get(`/api/v1/dwellers/${id}`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
      detailedDwellers.value[id] = response.data
      return detailedDwellers.value[id]
    } catch (error) {
      console.error(`Failed to fetch details for dweller ${id}`, error)
      return null
    }
  }

  async function generateDwellerInfo(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_with_ai/`, null, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
      detailedDwellers.value[id] = response.data
      toast.success('AI portrait generated successfully!')
      return detailedDwellers.value[id]
    } catch (error) {
      console.error(`Failed to generate image for dweller ${id}`, error)
      toast.error('Failed to generate AI portrait')
      return null
    }
  }

  async function assignDwellerToRoom(dwellerId: string, roomId: string, token: string): Promise<Dweller> {
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
      const dwellerIndex = dwellers.value.findIndex(d => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        dwellers.value[dwellerIndex] = { ...dwellers.value[dwellerIndex], room_id: roomId }
      }

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = response.data
      }

      toast.success('Dweller assigned to room successfully!')
      return response.data
    } catch (error) {
      console.error(`Failed to assign dweller ${dwellerId} to room ${roomId}`, error)
      toast.error('Failed to assign dweller to room')
      throw error
    }
  }

  async function unassignDwellerFromRoom(dwellerId: string, token: string): Promise<Dweller> {
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
      const dwellerIndex = dwellers.value.findIndex(d => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        dwellers.value[dwellerIndex] = { ...dwellers.value[dwellerIndex], room_id: null }
      }

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = response.data
      }

      toast.success('Dweller recalled successfully!')
      return response.data
    } catch (error) {
      console.error(`Failed to unassign dweller ${dwellerId}`, error)
      toast.error('Failed to recall dweller')
      throw error
    }
  }

  function setFilterStatus(status: DwellerStatus | 'all'): void {
    filterStatus.value = status
  }

  function setSortBy(sort: DwellerSortBy): void {
    sortBy.value = sort
  }

  function setSortDirection(direction: SortDirection): void {
    sortDirection.value = direction
  }

  function setViewMode(mode: 'list' | 'grid'): void {
    viewMode.value = mode
  }

  async function useStimpack(dwellerId: string, token: string): Promise<DwellerShort | null> {
    try {
      const response = await axios.post<DwellerShort>(
        `/api/v1/dwellers/${dwellerId}/use_stimpack`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      )

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = {
          ...detailedDwellers.value[dwellerId],
          ...response.data
        } as Dweller
      }

      // Update in list if exists
      const dwellerIndex = dwellers.value.findIndex(d => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        dwellers.value[dwellerIndex] = { ...dwellers.value[dwellerIndex], ...response.data }
      }

      toast.success('Stimpack used! Dweller healed.')
      return response.data
    } catch (error: unknown) {
      const errorMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to use stimpack'
      console.error(`Failed to use stimpack for dweller ${dwellerId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  async function useRadaway(dwellerId: string, token: string): Promise<DwellerShort | null> {
    try {
      const response = await axios.post<DwellerShort>(
        `/api/v1/dwellers/${dwellerId}/use_radaway`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      )

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = {
          ...detailedDwellers.value[dwellerId],
          ...response.data
        } as Dweller
      }

      // Update in list if exists
      const dwellerIndex = dwellers.value.findIndex(d => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        dwellers.value[dwellerIndex] = { ...dwellers.value[dwellerIndex], ...response.data }
      }

      toast.success('RadAway used! Radiation reduced.')
      return response.data
    } catch (error: unknown) {
      const errorMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to use RadAway'
      console.error(`Failed to use radaway for dweller ${dwellerId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  async function autoAssignToRoom(dwellerId: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(
        `/api/v1/dwellers/${dwellerId}/auto_assign`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      )

      // Update the dweller in the list
      const dwellerIndex = dwellers.value.findIndex(d => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        dwellers.value[dwellerIndex] = { ...dwellers.value[dwellerIndex], room_id: response.data.room_id }
      }

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = response.data
      }

      toast.success('Dweller auto-assigned to best matching room!')
      return response.data
    } catch (error: unknown) {
      const errorMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to auto-assign dweller'
      console.error(`Failed to auto-assign dweller ${dwellerId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  return {
    // State
    dwellers,
    detailedDwellers,
    isLoading,
    filterStatus,
    sortBy,
    sortDirection,
    viewMode,
    // Computed
    getDwellerStatus,
    dwellersWithStatus,
    getDwellersByStatus,
    filteredAndSortedDwellers,
    // Actions
    fetchDwellers,
    fetchDwellersByVault,
    fetchDwellerDetails,
    generateDwellerInfo,
    assignDwellerToRoom,
    unassignDwellerFromRoom,
    autoAssignToRoom,
    useStimpack,
    useRadaway,
    setFilterStatus,
    setSortBy,
    setSortDirection,
    setViewMode
  }
})
