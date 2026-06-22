import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import axios from '@/core/plugins/axios'
import type { Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'

export type DwellerStatus = 'idle' | 'working' | 'exploring' | 'questing' | 'training' | 'dead'
export type DwellerAgeGroup = 'child' | 'teen' | 'adult' | 'all'

export interface DwellerWithStatus extends DwellerShort {
  status: DwellerStatus
}

export type DwellerSortBy =
  | 'name'
  | 'level'
  | 'happiness'
  | 'strength'
  | 'perception'
  | 'endurance'
  | 'charisma'
  | 'intelligence'
  | 'agility'
  | 'luck'
export type SortDirection = 'asc' | 'desc'

export const useDwellerFilterStore = defineStore('dwellerFilter', () => {
  // State
  const dwellers = ref<DwellerShort[]>([])
  const detailedDwellers = ref<Record<string, Dweller | null>>({})
  const isLoading = ref(false)

  // Filter and sort state (persisted in localStorage)
  const filterStatus = useLocalStorage<DwellerStatus | 'all'>('dwellerFilterStatus', 'all')
  const filterAgeGroup = useLocalStorage<DwellerAgeGroup>('dwellerFilterAgeGroup', 'all')
  const sortBy = useLocalStorage<DwellerSortBy>('dwellerSortBy', 'name')
  const sortDirection = useLocalStorage<SortDirection>('dwellerSortDirection', 'asc')
  const viewMode = useLocalStorage<'list' | 'grid'>('dwellerViewMode', 'list')

  /**
   * Get dweller status - now directly from backend
   */
  function getDwellerStatus(dwellerId: string): DwellerStatus | null {
    const dweller = dwellers.value.find((d) => d.id === dwellerId)
    if (!dweller) return null

    // Backend now provides status directly
    return (dweller.status as DwellerStatus) || 'idle'
  }

  /**
   * Get all dwellers with their status (already provided by backend)
   */
  const dwellersWithStatus = computed((): DwellerWithStatus[] => {
    return dwellers.value.map((dweller) => ({
      ...dweller,
      status: (dweller.status as DwellerStatus) || 'idle',
    }))
  })

  /**
   * Get dwellers filtered by status - filters are now applied on backend
   */
  function getDwellersByStatus(status: DwellerStatus): DwellerWithStatus[] {
    return dwellers.value
      .filter((dweller) => dweller.status === status)
      .map((dweller) => ({
        ...dweller,
        status: (dweller.status as DwellerStatus) || 'idle',
      }))
  }

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
      } else if (sortBy.value === 'level' || sortBy.value === 'happiness') {
        comparison = a[sortBy.value] - b[sortBy.value]
      } else {
        // SPECIAL stats sorting
        comparison = a[sortBy.value] - b[sortBy.value]
      }

      return sortDirection.value === 'asc' ? comparison : -comparison
    })

    return result
  })

  async function fetchDwellers(vaultId: string, _token?: string): Promise<void> {
    console.warn('fetchDwellers is deprecated, use fetchDwellersByVault with vaultId')
    await fetchDwellersByVault(vaultId, _token || '')
  }

  async function fetchDwellersByVault(
    vaultId: string,
    token: string,
    options?: {
      status?: DwellerStatus | 'all'
      ageGroup?: DwellerAgeGroup
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
      if (options?.ageGroup && options.ageGroup !== 'all')
        params.append('age_group', options.ageGroup)
      if (options?.search) params.append('search', options.search)
      if (options?.sortBy) params.append('sort_by', options.sortBy)
      if (options?.order) params.append('order', options.order)
      if (options?.skip !== undefined) params.append('skip', options.skip.toString())
      if (options?.limit !== undefined) params.append('limit', options.limit.toString())

      const queryString = params.toString()
      const url = `/api/v1/dwellers/vault/${vaultId}/${queryString ? `?${queryString}` : ''}`

      const response = await axios.get(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      dwellers.value = response.data
    } catch (error) {
      handleStoreError(error, `Failed to fetch dwellers for vault ${vaultId}`)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchDwellerDetails(
    id: string,
    token: string,
    forceRefresh = false
  ): Promise<Dweller | null> {
    // Guard against invalid IDs (e.g. undefined before route resolves)
    if (!id || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
      return null
    }
    if (detailedDwellers.value[id] && !forceRefresh) return detailedDwellers.value[id] ?? null
    try {
      const response = await axios.get(`/api/v1/dwellers/${id}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      detailedDwellers.value[id] = response.data
      return detailedDwellers.value[id] ?? null
    } catch (error) {
      handleStoreError(error, `Failed to fetch details for dweller ${id}`)
      return null
    }
  }

  function setFilterStatus(status: DwellerStatus | 'all'): void {
    filterStatus.value = status
  }

  function setFilterAgeGroup(ageGroup: DwellerAgeGroup): void {
    filterAgeGroup.value = ageGroup
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

  return {
    dwellers,
    dwellersWithStatus,
    detailedDwellers,
    isLoading,
    filterStatus,
    filterAgeGroup,
    sortBy,
    sortDirection,
    viewMode,
    getDwellerStatus,
    getDwellersByStatus,
    filteredAndSortedDwellers,
    fetchDwellers,
    fetchDwellersByVault,
    fetchDwellerDetails,
    setFilterStatus,
    setFilterAgeGroup,
    setSortBy,
    setSortDirection,
    setViewMode,
  }
})
