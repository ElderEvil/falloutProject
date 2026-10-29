import { notifyErrorOnce } from '@/core/utils/errorHandler'
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { pregnancyApi } from '../api/pregnancy'
import type { Pregnancy, DeliveryResult } from '../models/pregnancy'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/types/utils'
import { formatDuration } from '@/core/utils/time'

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
      pregnancies.value = await pregnancyApi.getByVault(vaultId)
    } catch (error: unknown) {
      notifyErrorOnce(error, getErrorMessage(error))
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function getPregnancy(pregnancyId: string): Promise<Pregnancy | null> {
    try {
      return await pregnancyApi.get(pregnancyId)
    } catch (error: unknown) {
      notifyErrorOnce(error, getErrorMessage(error))
      return null
    }
  }

  async function deliverBaby(pregnancyId: string): Promise<DeliveryResult | null> {
    isLoading.value = true
    try {
      const result: DeliveryResult = await pregnancyApi.deliver(pregnancyId)

      // Update local state
      const index = pregnancies.value.findIndex((p) => p.id === pregnancyId)
      if (index !== -1 && pregnancies.value[index]) {
        pregnancies.value[index]!.status = 'delivered'
      }

      toast.success(result.message)
      return result
    } catch (error: unknown) {
      notifyErrorOnce(error, getErrorMessage(error))
      return null
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Format time remaining as human-readable string
   */
  function formatTimeRemaining(seconds: number): string {
    return formatDuration(seconds, { includeSeconds: true })
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
    formatTimeRemaining,
    clearPregnancies,
  }
})
