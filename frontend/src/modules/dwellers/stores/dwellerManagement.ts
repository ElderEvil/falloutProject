import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'
import type { Dweller } from '../models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useGaryMode } from '@/core/composables/useGaryMode'
import { useDwellerFilterStore } from './dwellerFilter'
import { getLineage, type LineageResponse } from '../services/lineageService'

type AutoAssignResponse = components['schemas']['AutoAssignResponse']
type AutoAssignAgeGroup = components['schemas']['AgeGroupEnum']

export const useDwellerManagementStore = defineStore('dwellerManagement', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()

  const lineage = ref<LineageResponse | null>(null)
  const isLoadingLineage = ref(false)
  let lineageRequestSeq = 0

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
      const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && filterStore.dwellers[dwellerIndex]) {
        filterStore.dwellers[dwellerIndex] = {
          ...filterStore.dwellers[dwellerIndex]!,
          room_id: roomId,
        }
      }

      // Update detailed dweller if cached
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = response.data
      }

      return response.data
    } catch (error) {
      handleStoreError(error, `Failed to assign dweller ${dwellerId} to room ${roomId}`)
      throw error
    }
  }

  async function softDeleteDweller(dwellerId: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post<Dweller>(`/api/v1/dwellers/${dwellerId}/soft-delete`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      // Remove the dweller from the active list and detail cache
      filterStore.dwellers = filterStore.dwellers.filter((d) => d.id !== dwellerId)
      delete filterStore.detailedDwellers[dwellerId]

      toast.success('Dweller moved to the Trading Post pool')
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to soft-delete dweller'
      handleStoreError(error, `Failed to soft-delete dweller ${dwellerId}`)
      toast.error(errorMessage)
      return null
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
      const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && filterStore.dwellers[dwellerIndex]) {
        filterStore.dwellers[dwellerIndex] = {
          ...filterStore.dwellers[dwellerIndex]!,
          room_id: null,
          status: response.data.status,
        }
      }

      // Update detailed dweller if cached
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = response.data
      }

      return response.data
    } catch (error) {
      handleStoreError(error, `Failed to unassign dweller ${dwellerId}`)
      throw error
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
      const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && filterStore.dwellers[dwellerIndex]) {
        filterStore.dwellers[dwellerIndex] = {
          ...filterStore.dwellers[dwellerIndex]!,
          room_id: response.data.room_id,
        }
      }

      // Update detailed dweller if cached
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = response.data
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
      handleStoreError(error, `Failed to auto-assign dweller ${dwellerId}`)
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
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = response.data
      }

      // Update in list if present
      const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && filterStore.dwellers[dwellerIndex]) {
        filterStore.dwellers[dwellerIndex] = {
          ...filterStore.dwellers[dwellerIndex]!,
          first_name: response.data.first_name,
        }
      }

      toast.success('Dweller renamed successfully!')

      // Trigger Gary easter egg if renamed to "Gary" (case-insensitive)
      if (firstName.toLowerCase() === 'gary') {
        const { triggerGaryMode } = useGaryMode()
        triggerGaryMode()
        toast.info('VAULT 108 PROTOCOL ACTIVATED', 5000)
      }

      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to rename dweller'
      handleStoreError(error, `Failed to rename dweller ${dwellerId}`)
      toast.error(errorMessage)
      return null
    }
  }

  async function updateVisualAttributes(
    dwellerId: string,
    visualAttributes: Record<string, unknown>,
    token: string
  ): Promise<Dweller | null> {
    try {
      const response = await axios.put(
        `/api/v1/dwellers/${dwellerId}`,
        { visual_attributes: visualAttributes },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Update detailed dweller if cached
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = response.data
      }

      toast.success('Appearance updated successfully!')
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to update appearance'
      handleStoreError(error, `Failed to update appearance for dweller ${dwellerId}`)
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
      await filterStore.fetchDwellersByVault(vaultId, token)

      toast.success(`Unassigned ${response.data.unassigned_count} dwellers`)
      return response.data
    } catch (error: unknown) {
      const errorMessage =
        (
          error as {
            response?: { data?: { detail?: string } }
          }
        )?.response?.data?.detail || 'Failed to unassign all dwellers'
      handleStoreError(error, `Failed to unassign all dwellers for vault ${vaultId}`)
      toast.error(errorMessage)
      return null
    }
  }

  /** Shared auto-assign request: POST with optional filters, refetch, toast. */
  async function autoAssignDwellers(
    endpoint: 'auto-assign-production' | 'auto-assign-all',
    vaultId: string,
    token: string,
    filters: { ageGroup?: AutoAssignAgeGroup } | undefined,
    successSuffix: string,
    failureLabel: string
  ): Promise<AutoAssignResponse | null> {
    try {
      const queryString = filters?.ageGroup ? `?age_group=${filters.ageGroup}` : ''
      const response = await axios.post<AutoAssignResponse>(
        `/api/v1/vaults/${vaultId}/dwellers/${endpoint}${queryString}`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Refetch dwellers to update UI
      await filterStore.fetchDwellersByVault(vaultId, token, {
        status: filterStore.filterStatus,
        ageGroup: filterStore.filterAgeGroup,
        sortBy: filterStore.sortBy,
        order: filterStore.sortDirection,
      })

      toast.success(`Assigned ${response.data.assigned_count} dwellers ${successSuffix}`)
      return response.data
    } catch (error) {
      const errorMessage = handleStoreError(error, `${failureLabel} for vault ${vaultId}`)
      toast.error(errorMessage || failureLabel)
      return null
    }
  }

  function autoAssignProductionDwellers(
    vaultId: string,
    token: string,
    filters?: { ageGroup?: AutoAssignAgeGroup }
  ) {
    return autoAssignDwellers(
      'auto-assign-production',
      vaultId,
      token,
      filters,
      'to production rooms!',
      'Failed to auto-assign dwellers to production rooms'
    )
  }

  function autoAssignAllDwellers(vaultId: string, token: string, filters?: { ageGroup?: AutoAssignAgeGroup }) {
    return autoAssignDwellers(
      'auto-assign-all',
      vaultId,
      token,
      filters,
      'to rooms!',
      'Failed to auto-assign dwellers'
    )
  }

  async function fetchLineage(dwellerId: string): Promise<LineageResponse | null> {
    const seq = ++lineageRequestSeq
    isLoadingLineage.value = true
    try {
      const result = await getLineage(dwellerId)
      if (seq === lineageRequestSeq) {
        lineage.value = result
        return result
      }
      return null
    } catch (error: unknown) {
      if (seq === lineageRequestSeq) {
        handleStoreError(error, 'Failed to fetch lineage')
      }
      return null
    } finally {
      if (seq === lineageRequestSeq) {
        isLoadingLineage.value = false
      }
    }
  }

  return {
    assignDwellerToRoom,
    unassignDwellerFromRoom,
    softDeleteDweller,
    autoAssignToRoom,
    renameDweller,
    updateVisualAttributes,
    unassignAllDwellers,
    autoAssignProductionDwellers,
    autoAssignAllDwellers,
    lineage,
    isLoadingLineage,
    fetchLineage,
  }
})
