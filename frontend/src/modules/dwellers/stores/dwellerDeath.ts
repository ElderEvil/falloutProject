import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type { DwellerDead, DwellerReviveResponse, RevivalCostResponse } from '../models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useDwellerFilterStore } from './dwellerFilter'

export const useDwellerDeathStore = defineStore('dwellerDeath', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()

  const deadDwellers = ref<DwellerDead[]>([])
  const graveyardDwellers = ref<DwellerDead[]>([])
  const isDeadLoading = ref(false)

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
      handleStoreError(error, `Failed to fetch dead dwellers for vault ${vaultId}`)
      return []
    } finally {
      isDeadLoading.value = false
    }
  }

  /**
   * Fetch graveyard (permanently dead) dwellers for a vault
   */
  async function fetchGraveyardDwellers(vaultId: string, token: string): Promise<DwellerDead[]> {
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
      handleStoreError(error, `Failed to fetch graveyard for vault ${vaultId}`)
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
      handleStoreError(error, `Failed to get revival cost for dweller ${dwellerId}`)
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
      const existingIndex = filterStore.dwellers.findIndex((d) => d.id === dwellerId)
      if (existingIndex !== -1) {
        // Replace existing stale entry with revived dweller data
        filterStore.dwellers[existingIndex] =
          revivedDweller as unknown as import('../models/dweller').DwellerShort
      } else {
        // Type cast needed since DwellerRead may have slightly different shape than DwellerShort
        filterStore.dwellers.push(
          revivedDweller as unknown as import('../models/dweller').DwellerShort
        )
      }

      // Also update cached detailed dweller if present
      if (dwellerId in filterStore.detailedDwellers) {
        filterStore.detailedDwellers[dwellerId] =
          revivedDweller as unknown as import('../models/dweller').Dweller
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
      handleStoreError(error, `Failed to revive dweller ${dwellerId}`)
      toast.error(errorMessage)
      return null
    }
  }

  return {
    deadDwellers,
    graveyardDwellers,
    isDeadLoading,
    fetchDeadDwellers,
    fetchGraveyardDwellers,
    getRevivalCost,
    reviveDweller,
  }
})
