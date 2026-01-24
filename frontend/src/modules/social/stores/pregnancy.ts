import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type { Pregnancy, DeliveryResult } from '../models/pregnancy'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/types/utils'

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
      const response = await axios.get(`/api/v1/pregnancies/vault/${vaultId}`)
      pregnancies.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch pregnancies:', error)
      toast.error(getErrorMessage(error))
    } finally {
      isLoading.value = false
    }
  }

  async function getPregnancy(pregnancyId: string): Promise<Pregnancy | null> {
    try {
      const response = await axios.get(`/api/v1/pregnancies/${pregnancyId}`)
      return response.data
    } catch (error: unknown) {
      console.error('Failed to fetch pregnancy:', error)
      toast.error(getErrorMessage(error))
      return null
    }
  }

  async function deliverBaby(pregnancyId: string): Promise<DeliveryResult | null> {
    isLoading.value = true
    try {
      const response = await axios.post(`/api/v1/pregnancies/${pregnancyId}/deliver`)
      const result: DeliveryResult = response.data

      // Update local state
      const index = pregnancies.value.findIndex((p) => p.id === pregnancyId)
      if (index !== -1 && pregnancies.value[index]) {
        pregnancies.value[index]!.status = 'delivered'
      }

      toast.success(result.message)
      return result
    } catch (error: unknown) {
      console.error('Failed to deliver baby:', error)
      toast.error(getErrorMessage(error))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function forceConception(motherId: string, fatherId: string): Promise<Pregnancy | null> {
    isLoading.value = true
    try {
      const response = await axios.post(
        `/api/v1/pregnancies/debug/force-conception`,
        null,
        {
          params: {
            mother_id: motherId,
            father_id: fatherId
          }
        }
      )
      const pregnancy: Pregnancy = response.data
      pregnancies.value.push(pregnancy)
      toast.success('Force conception successful!')
      return pregnancy
    } catch (error: unknown) {
      console.error('Failed to force conception:', error)
      toast.error(getErrorMessage(error))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function acceleratePregnancy(pregnancyId: string): Promise<boolean> {
    isLoading.value = true
    try {
      await axios.post(`/api/v1/pregnancies/${pregnancyId}/debug/accelerate`)

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
      console.error('Failed to accelerate pregnancy:', error)
      toast.error(getErrorMessage(error))
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
