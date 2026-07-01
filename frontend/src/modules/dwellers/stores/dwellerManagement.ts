import { defineStore, acceptHMRUpdate } from 'pinia'
import * as http from '@/core/plugins/httpClient'
import type { Dweller } from '../models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useGaryMode } from '@/core/composables/useGaryMode'
import { useDwellerFilterStore } from './dwellerFilter'

export const useDwellerManagementStore = defineStore('dwellerManagement', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()

  async function assignDwellerToRoom(
    dwellerId: string,
    roomId: string,
    token: string
  ): Promise<Dweller> {
    try {
      const response = await http.apiPost(`/api/v1/dwellers/${dwellerId}/move_to/${roomId}`, null, {
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
        filterStore.detailedDwellers[dwellerId] = response
      }

      return response
    } catch (error) {
      handleStoreError(error, `Failed to assign dweller ${dwellerId} to room ${roomId}`)
      throw error
    }
  }

  async function unassignDwellerFromRoom(dwellerId: string, token: string): Promise<Dweller> {
    try {
      // Move dweller to null room (unassign)
      const response = await http.apiPut(
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
          status: response.status,
        }
      }

      // Update detailed dweller if cached
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = response
      }

      return response
    } catch (error) {
      handleStoreError(error, `Failed to unassign dweller ${dwellerId}`)
      throw error
    }
  }

  async function autoAssignToRoom(dwellerId: string, token: string): Promise<Dweller | null> {
    try {
      const response = await http.apiPost(`/api/v1/dwellers/${dwellerId}/auto_assign`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      // Update the dweller in the list
      const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && filterStore.dwellers[dwellerIndex]) {
        filterStore.dwellers[dwellerIndex] = {
          ...filterStore.dwellers[dwellerIndex]!,
          room_id: response.room_id,
        }
      }

      // Update detailed dweller if cached
      if (filterStore.detailedDwellers[dwellerId]) {
        filterStore.detailedDwellers[dwellerId] = response
      }

      toast.success('Dweller auto-assigned to best matching room!')
      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to auto-assign dweller'
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
      const response = await http.apiPatch(
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
        filterStore.detailedDwellers[dwellerId] = response
      }

      // Update in list if present
      const dwellerIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (dwellerIndex !== -1 && filterStore.dwellers[dwellerIndex]) {
        filterStore.dwellers[dwellerIndex] = {
          ...filterStore.dwellers[dwellerIndex]!,
          first_name: response.first_name,
        }
      }

      toast.success('Dweller renamed successfully!')

      // Trigger Gary easter egg if renamed to "Gary" (case-insensitive)
      if (firstName.toLowerCase() === 'gary') {
        const { triggerGaryMode } = useGaryMode()
        triggerGaryMode()
        toast.info('VAULT 108 PROTOCOL ACTIVATED', { duration: 5000 })
      }

      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to rename dweller'
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
      const response = await http.apiPut(
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
        filterStore.detailedDwellers[dwellerId] = response
      }

      toast.success('Appearance updated successfully!')
      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to update appearance'
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
      const response = await http.apiPost<{ unassigned_count: number }>(
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

      toast.success(`Unassigned ${response.unassigned_count} dwellers`)
      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to unassign all dwellers'
      handleStoreError(error, `Failed to unassign all dwellers for vault ${vaultId}`)
      toast.error(errorMessage)
      return null
    }
  }

  async function autoAssignAllDwellers(
    vaultId: string,
    token: string
  ): Promise<{ assigned_count: number; assignments: any[] } | null> {
    try {
      const response = await http.apiPost<{ assigned_count: number; assignments: any[] }>(
        `/api/v1/vaults/${vaultId}/dwellers/auto-assign-all`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      // Refetch dwellers to update UI
      await filterStore.fetchDwellersByVault(vaultId, token)

      toast.success(`Assigned ${response.assigned_count} dwellers to rooms!`)
      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to auto-assign dwellers'
      handleStoreError(error, `Failed to auto-assign dwellers for vault ${vaultId}`)
      toast.error(errorMessage)
      return null
    }
  }

  return {
    assignDwellerToRoom,
    unassignDwellerFromRoom,
    autoAssignToRoom,
    renameDweller,
    updateVisualAttributes,
    unassignAllDwellers,
    autoAssignAllDwellers,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDwellerManagementStore, import.meta.hot))
}
