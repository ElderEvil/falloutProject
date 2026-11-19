import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import * as deathApi from '../api/death'
import type { DwellerDead, DwellerReviveResponse, RevivalCostResponse } from '../models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useDwellerFilterStore } from './dwellerFilter'
import { useVaultStore } from '@/modules/vault/stores/vault'

export const useDwellerDeathStore = defineStore('dwellerDeath', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()
  const vaultStore = useVaultStore()

  const deadDwellers = ref<DwellerDead[]>([])
  const graveyardDwellers = ref<DwellerDead[]>([])
  const deadLoadingCount = ref(0)
  const isDeadLoading = computed(() => deadLoadingCount.value > 0)
  let fetchDeadDwellersRequestSequence = 0

  /**
   * Fetch dead dwellers (revivable) for a vault
   */
  async function fetchDeadDwellers(vaultId: string): Promise<DwellerDead[]> {
    const requestSequence = ++fetchDeadDwellersRequestSequence
    deadLoadingCount.value++
    try {
      const data = await deathApi.getDeadDwellers(vaultId)
      if (requestSequence === fetchDeadDwellersRequestSequence) {
        deadDwellers.value = data
      }
      return data
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
  async function fetchGraveyardDwellers(vaultId: string): Promise<DwellerDead[]> {
    deadLoadingCount.value++
    try {
      const data = await deathApi.getGraveyardDwellers(vaultId)
      graveyardDwellers.value = data
      return data
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
  async function getRevivalCost(dwellerId: string): Promise<RevivalCostResponse | null> {
    try {
      return await deathApi.getRevivalCost(dwellerId)
    } catch (error: unknown) {
      handleStoreError(error, `Failed to get revival cost for dweller ${dwellerId}`)
      return null
    }
  }

  /**
   * Revive a dead dweller
   */
  async function reviveDweller(dwellerId: string): Promise<DwellerReviveResponse | null> {
    const vaultId = vaultStore.activeVaultId
    const generation = vaultStore.currentSessionGeneration()
    try {
      const data = await deathApi.reviveDweller(dwellerId)

      if (vaultStore.currentSessionGeneration() !== generation) return data

      // Remove from dead dwellers list
      deadDwellers.value = deadDwellers.value.filter((d) => d.id !== dwellerId)

      // Update or add revived dweller to main list
      const revivedDweller = data.dweller
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

      if (vaultId) {
        vaultStore.applyCaps(vaultId, data.remaining_caps)
      }

      toast.success(`${revivedDweller.first_name} has been revived! Caps spent: ${data.caps_spent}`)
      return data
    } catch (error: unknown) {
      handleStoreError(error, `Failed to revive dweller ${dwellerId}`)
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
