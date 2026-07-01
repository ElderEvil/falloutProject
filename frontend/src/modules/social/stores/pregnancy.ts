import { ref, computed } from 'vue'
import { defineStore, acceptHMRUpdate } from 'pinia'
import * as http from '@/core/plugins/httpClient'
import type { Pregnancy, DeliveryResult } from '../models/pregnancy'
import { useToast } from '@/core/composables/useToast'
import { handleStoreError } from '@/core/utils/errorHandler'

export const usePregnancyStore = defineStore('pregnancy', () => {
  const toast = useToast()

  // State
  const pregnancies = ref<Pregnancy[]>([])
  const isLoading = ref(false)

  // Computed
  const activePregnancies = computed(() => {
    return pregnancies.value.filter((p) => p.status === 'pregnant')
  })

  const duePregnancies = computed(() => {
    return pregnancies.value.filter((p) => p.is_due)
  })

  const getPregnancyByMother = computed(() => {
    return (motherId: string): Pregnancy | undefined => {
      return pregnancies.value.find((p) => p.mother_id === motherId && p.status === 'pregnant')
    }
  })

  // Actions
  async function fetchVaultPregnancies(vaultId: string) {
    isLoading.value = true
    try {
      pregnancies.value = await http.apiGet<Pregnancy[]>(`/api/v1/pregnancies/vault/${vaultId}`)
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to fetch pregnancies'))
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function getPregnancy(pregnancyId: string): Promise<Pregnancy | null> {
    try {
      return await http.apiGet<Pregnancy>(`/api/v1/pregnancies/${pregnancyId}`)
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to fetch pregnancy'))
      return null
    }
  }

  async function deliverBaby(pregnancyId: string): Promise<DeliveryResult | null> {
    isLoading.value = true
    try {
      const result = await http.apiPost<DeliveryResult>(`/api/v1/pregnancies/${pregnancyId}/deliver`)

      // Update local state
      const index = pregnancies.value.findIndex((p) => p.id === pregnancyId)
      if (index !== -1 && pregnancies.value[index]) {
        pregnancies.value[index]!.status = 'delivered'
      }

      toast.success(result.message)
      return result
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to deliver baby'))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function forceConception(motherId: string, fatherId: string): Promise<Pregnancy | null> {
    isLoading.value = true
    try {
      const params = new URLSearchParams({ mother_id: motherId, father_id: fatherId })
      const pregnancy = await http.apiPost<Pregnancy>(
        `/api/v1/pregnancies/debug/force-conception?${params}`
      )
      pregnancies.value.push(pregnancy)
      toast.success('Force conception successful!')
      return pregnancy
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to force conception'))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function acceleratePregnancy(pregnancyId: string): Promise<boolean> {
    isLoading.value = true
    try {
      await http.apiPost(`/api/v1/pregnancies/${pregnancyId}/debug/accelerate`)

      // Update local state to reflect changes (e.g. make it due)
      // Since backend logic is complex, best to re-fetch the pregnancy or just set is_due if we know it
      // But typically accelerate makes it ready for delivery.

      const index = pregnancies.value.findIndex((p) => p.id === pregnancyId)
      if (index !== -1 && pregnancies.value[index]) {
        pregnancies.value[index]!.is_due = true
        // Maybe refresh the whole list to be safe?
      }

      toast.success('Pregnancy accelerated!')
      return true
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to accelerate pregnancy'))
      return false
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Format time remaining as human-readable string
   */
  function formatTimeRemaining(seconds: number): string {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60

    if (hours > 0) {
      return `${hours}h ${minutes}m`
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`
    } else {
      return `${secs}s`
    }
  }

  function clearPregnancies() {
    pregnancies.value = []
  }

  return {
    // State
    pregnancies,
    isLoading,

    // Computed
    activePregnancies,
    duePregnancies,
    getPregnancyByMother,

    // Actions
    fetchVaultPregnancies,
    getPregnancy,
    deliverBaby,
    forceConception,
    acceleratePregnancy,
    formatTimeRemaining,
    clearPregnancies,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(usePregnancyStore, import.meta.hot))
}
