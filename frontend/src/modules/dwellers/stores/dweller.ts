import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import axios from '@/core/plugins/axios'
import type {
  Dweller,
  DwellerShort,
  DwellerDead,
  DwellerReviveResponse,
  RevivalCostResponse,
} from '../models/dweller'
import { useToast } from '@/core/composables/useToast'
import { useGaryMode } from '@/core/composables/useGaryMode'

export type DwellerStatus = 'idle' | 'working' | 'exploring' | 'questing' | 'training' | 'resting' | 'dead'

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

export const useDwellerStore = defineStore('dweller', () => {
  const toast = useToast()

  // State
  const dwellers = ref<DwellerShort[]>([])
  const detailedDwellers = ref<Record<string, Dweller | null>>({})
  const deadDwellers = ref<DwellerDead[]>([])
  const graveyardDwellers = ref<DwellerDead[]>([])
  const isLoading = ref(false)
  const isDeadLoading = ref(false)

  // Filter and sort state (persisted in localStorage)
  const filterStatus = useLocalStorage<DwellerStatus | 'all'>('dwellerFilterStatus', 'all')
  const sortBy = useLocalStorage<DwellerSortBy>('dwellerSortBy', 'name')
  const sortDirection = useLocalStorage<SortDirection>('dwellerSortDirection', 'asc')
  const viewMode = useLocalStorage<'list' | 'grid'>('dwellerViewMode', 'list')

  /**
   * Get dweller status - now directly from backend
   */
  const getDwellerStatus = computed(() => {
    return (dwellerId: string): DwellerStatus | null => {
      const dweller = dwellers.value.find((d) => d.id === dwellerId)
      if (!dweller) return null

      // Backend now provides status directly
      return (dweller.status as DwellerStatus) || 'idle'
    }
  })

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
  const getDwellersByStatus = computed(() => {
    return (status: DwellerStatus): DwellerWithStatus[] => {
      return dwellers.value
        .filter((dweller) => dweller.status === status)
        .map((dweller) => ({
          ...dweller,
          status: (dweller.status as DwellerStatus) || 'idle',
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
          Authorization: `Bearer ${token}`,
        },
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
      console.error(`Failed to fetch details for dweller ${id}`, error)
      return null
    }
  }

  async function generateDwellerInfo(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_with_ai/`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      detailedDwellers.value[id] = response.data
      toast.success('AI portrait generated successfully!')
      return detailedDwellers.value[id] ?? null
    } catch (error) {
      console.error(`Failed to generate image for dweller ${id}`, error)
      toast.error('Failed to generate AI portrait')
      return null
    }
  }

  async function generateDwellerBio(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_backstory/`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      detailedDwellers.value[id] = response.data
      toast.success('Biography generated successfully!')
      return detailedDwellers.value[id] ?? null
    } catch (error) {
      console.error(`Failed to generate biography for dweller ${id}`, error)
      toast.error('Failed to generate biography')
      return null
    }
  }

  async function generateDwellerPortrait(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_photo/`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      detailedDwellers.value[id] = response.data
      toast.success('Portrait generated successfully!')
      return detailedDwellers.value[id] ?? null
    } catch (error) {
      console.error(`Failed to generate portrait for dweller ${id}`, error)
      toast.error('Failed to generate portrait')
      return null
    }
  }

  async function generateDwellerAppearance(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(
        `/api/v1/dwellers/${id}/generate_visual_attributes/`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      detailedDwellers.value[id] = response.data
      toast.success('Appearance generated successfully!')
      return detailedDwellers.value[id] ?? null
    } catch (error) {
      console.error(`Failed to generate appearance for dweller ${id}`, error)
      toast.error('Failed to generate appearance')
      return null
    }
  }

  async function assignDwellerToRoom(
    dwellerId: string,
    roomId: string,
    token: string
  ): Promise<Dweller> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${dwellerId}/move_to/${roomId}`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      // Update the dweller in the list
      const dwellerIndex = dwellers.value.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && dwellers.value[dwellerIndex]) {
        dwellers.value[dwellerIndex] = { ...dwellers.value[dwellerIndex]!, room_id: roomId }
      }

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = response.data
      }

      return response.data
    } catch (error) {
      console.error(`Failed to assign dweller ${dwellerId} to room ${roomId}`, error)
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
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Update the dweller in the list with full response data
      const dwellerIndex = dwellers.value.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && dwellers.value[dwellerIndex]) {
        dwellers.value[dwellerIndex] = {
          ...dwellers.value[dwellerIndex]!,
          room_id: null,
          status: response.data.status,
        }
      }

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = response.data
      }

      return response.data
    } catch (error) {
      console.error(`Failed to unassign dweller ${dwellerId}`, error)
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
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = {
          ...detailedDwellers.value[dwellerId],
          ...response.data,
        } as Dweller
      }

      // Update in list if exists
      const dwellerIndex = dwellers.value.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        dwellers.value[dwellerIndex] = { ...dwellers.value[dwellerIndex], ...response.data }
      }

      toast.success('Stimpack used! Dweller healed.')
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to use stimpack'
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
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = {
          ...detailedDwellers.value[dwellerId],
          ...response.data,
        } as Dweller
      }

      // Update in list if exists
      const dwellerIndex = dwellers.value.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1) {
        dwellers.value[dwellerIndex] = { ...dwellers.value[dwellerIndex], ...response.data }
      }

      toast.success('RadAway used! Radiation reduced.')
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to use RadAway'
      console.error(`Failed to use radaway for dweller ${dwellerId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  async function autoAssignToRoom(dwellerId: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${dwellerId}/auto_assign`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      // Update the dweller in the list
      const dwellerIndex = dwellers.value.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && dwellers.value[dwellerIndex]) {
        dwellers.value[dwellerIndex] = {
          ...dwellers.value[dwellerIndex]!,
          room_id: response.data.room_id,
        }
      }

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = response.data
      }

      toast.success('Dweller auto-assigned to best matching room!')
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to auto-assign dweller'
      console.error(`Failed to auto-assign dweller ${dwellerId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  async function renameDweller(
    dwellerId: string,
    firstName: string,
    token: string
  ): Promise<Dweller | null> {
    try {
      const response = await axios.patch(
        `/api/v1/dwellers/${dwellerId}/rename`,
        { first_name: firstName },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Update detailed dweller if cached
      if (detailedDwellers.value[dwellerId]) {
        detailedDwellers.value[dwellerId] = response.data
      }

      // Update in list if present
      const dwellerIndex = dwellers.value.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && dwellers.value[dwellerIndex]) {
        dwellers.value[dwellerIndex] = {
          ...dwellers.value[dwellerIndex]!,
          first_name: response.data.first_name,
        }
      }

      toast.success('Dweller renamed successfully!')

      // Trigger Gary easter egg if renamed to "Gary" (case-insensitive)
      if (firstName.toLowerCase() === 'gary') {
        const { triggerGaryMode } = useGaryMode()
        triggerGaryMode()
        toast.info('VAULT 108 PROTOCOL ACTIVATED', { duration: 5000 })
      }

      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to rename dweller'
      console.error(`Failed to rename dweller ${dwellerId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  async function unassignAllDwellers(
    vaultId: string,
    token: string
  ): Promise<{ unassigned_count: number } | null> {
    try {
      const response = await axios.post<{ unassigned_count: number }>(
        `/api/v1/vaults/${vaultId}/dwellers/unassign-all`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Refetch dwellers to update UI
      await fetchDwellersByVault(vaultId, token)

      toast.success(`Unassigned ${response.data.unassigned_count} dwellers`)
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to unassign all dwellers'
      console.error(`Failed to unassign all dwellers for vault ${vaultId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  async function autoAssignAllDwellers(
    vaultId: string,
    token: string
  ): Promise<{ assigned_count: number; assignments: any[] } | null> {
    try {
      const response = await axios.post<{ assigned_count: number; assignments: any[] }>(
        `/api/v1/vaults/${vaultId}/dwellers/auto-assign-all`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Refetch dwellers to update UI
      await fetchDwellersByVault(vaultId, token)

      toast.success(`Assigned ${response.data.assigned_count} dwellers to rooms!`)
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to auto-assign dwellers'
      console.error(`Failed to auto-assign dwellers for vault ${vaultId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  // ================================
  // Death System Actions
  // ================================

  /**
   * Fetch dead dwellers (revivable) for a vault
   */
  async function fetchDeadDwellers(vaultId: string, token: string): Promise<DwellerDead[]> {
    isDeadLoading.value = true
    try {
      const response = await axios.get<DwellerDead[]>(`/api/v1/dwellers/vault/${vaultId}/dead`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      deadDwellers.value = response.data
      return response.data
    } catch (error) {
      console.error(`Failed to fetch dead dwellers for vault ${vaultId}`, error)
      return []
    } finally {
      isDeadLoading.value = false
    }
  }

  /**
   * Fetch graveyard (permanently dead) dwellers for a vault
   */
  async function fetchGraveyard(vaultId: string, token: string): Promise<DwellerDead[]> {
    isDeadLoading.value = true
    try {
      const response = await axios.get<DwellerDead[]>(
        `/api/v1/dwellers/vault/${vaultId}/graveyard`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      graveyardDwellers.value = response.data
      return response.data
    } catch (error) {
      console.error(`Failed to fetch graveyard for vault ${vaultId}`, error)
      return []
    } finally {
      isDeadLoading.value = false
    }
  }

  /**
   * Get revival cost for a dead dweller
   */
  async function getRevivalCost(
    dwellerId: string,
    token: string
  ): Promise<RevivalCostResponse | null> {
    try {
      const response = await axios.get<RevivalCostResponse>(
        `/api/v1/dwellers/${dwellerId}/revival_cost`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to get revival cost'
      console.error(`Failed to get revival cost for dweller ${dwellerId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  /**
   * Revive a dead dweller
   */
  async function reviveDweller(
    dwellerId: string,
    token: string
  ): Promise<DwellerReviveResponse | null> {
    try {
      const response = await axios.post<DwellerReviveResponse>(
        `/api/v1/dwellers/${dwellerId}/revive`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Remove from dead dwellers list
      deadDwellers.value = deadDwellers.value.filter((d) => d.id !== dwellerId)

      // Update or add revived dweller to main list
      const revivedDweller = response.data.dweller
      const existingIndex = dwellers.value.findIndex((d) => d.id === dwellerId)
      if (existingIndex !== -1) {
        // Replace existing stale entry with revived dweller data
        dwellers.value[existingIndex] = revivedDweller as unknown as DwellerShort
      } else {
        // Type cast needed since DwellerRead may have slightly different shape than DwellerShort
        dwellers.value.push(revivedDweller as unknown as DwellerShort)
      }

      // Also update cached detailed dweller if present
      if (dwellerId in detailedDwellers.value) {
        detailedDwellers.value[dwellerId] = revivedDweller as unknown as Dweller
      }

      toast.success(
        `${revivedDweller.first_name} has been revived! Caps spent: ${response.data.caps_spent}`
      )
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to revive dweller'
      console.error(`Failed to revive dweller ${dwellerId}`, error)
      toast.error(errorMessage)
      return null
    }
  }

  return {
    dwellers,
    dwellersWithStatus,
    detailedDwellers,
    deadDwellers,
    graveyardDwellers,
    isLoading,
    isDeadLoading,
    filterStatus,
    sortBy,
    sortDirection,
    viewMode,
    getDwellerStatus,
    getDwellersByStatus,
    filteredAndSortedDwellers,
    fetchDwellers,
    fetchDwellersByVault,
    fetchDwellerDetails,
    generateDwellerInfo,
    generateDwellerBio,
    generateDwellerPortrait,
    generateDwellerAppearance,
    assignDwellerToRoom,
    unassignDwellerFromRoom,
    renameDweller,
    setFilterStatus,
    setSortBy,
    setSortDirection,
    setViewMode,
    useStimpack,
    useRadaway,
    autoAssignToRoom,
    unassignAllDwellers,
    autoAssignAllDwellers,
    fetchDeadDwellers,
    fetchGraveyardDwellers: fetchGraveyard,
    getRevivalCost,
    reviveDweller,
  }
})
