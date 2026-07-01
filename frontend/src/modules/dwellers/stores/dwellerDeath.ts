import { ref, computed } from 'vue'
import { defineStore, acceptHMRUpdate } from 'pinia'
import * as http from '@/core/plugins/httpClient'
import type { DwellerDead, DwellerReviveResponse, RevivalCostResponse } from '../models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useDwellerFilterStore } from './dwellerFilter'

export const useDwellerDeathStore = defineStore('dwellerDeath', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()

  const deadDwellers = ref<DwellerDead[]>([])
  const graveyardDwellers = ref<DwellerDead[]>([])
  const deadLoadingCount = ref(0)
  const isDeadLoading = computed(() => deadLoadingCount.value > 0)

  /**
   * Fetch dead dwellers (revivable) for a vault
   */
  async function fetchDeadDwellers(vaultId: string, token: string): Promise<DwellerDead[]> {
    deadLoadingCount.value++
    try {
      const response = await http.apiGet<DwellerDead[]>(`/api/v1/dwellers/vault/${vaultId}/dead`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useDwellerDeathStore, import.meta.hot))
}

      deadDwellers.value = response
      return response
    } catch (error) {
      handleStoreError(error, `Failed to fetch dead dwellers for vault ${vaultId}`)
      return []
    } finally {
      deadLoadingCount.value--
    }
  }

  /**
   * Fetch graveyard (permanently dead) dwellers for a vault
   */
  async function fetchGraveyardDwellers(vaultId: string, token: string): Promise<DwellerDead[]> {
    deadLoadingCount.value++
    try {
      const response = await http.apiGet<DwellerDead[]>(
        `/api/v1/dwellers/vault/${vaultId}/graveyard`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      graveyardDwellers.value = response
      return response
    } catch (error) {
      handleStoreError(error, `Failed to fetch graveyard for vault ${vaultId}`)
      return []
    } finally {
      deadLoadingCount.value--
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
      const response = await http.apiGet<RevivalCostResponse>(
        `/api/v1/dwellers/${dwellerId}/revival_cost`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to get revival cost'
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
      const response = await http.apiPost<DwellerReviveResponse>(
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
      const revivedDweller = response.dweller
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
        `${revivedDweller.first_name} has been revived! Caps spent: ${response.caps_spent}`
      )
      return response
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to revive dweller'
      handleStoreError(error, `Failed to revive dweller ${dwellerId}`)
      toast.error(errorMessage)
      return null
    }
  }

  return {
    deadDwellers,
    graveyardDwellers,
    deadLoadingCount,
    isDeadLoading,
    fetchDeadDwellers,
    fetchGraveyardDwellers,
    getRevivalCost,
    reviveDweller,
  }
})
