import { ref } from 'vue'
import { defineStore, acceptHMRUpdate } from 'pinia'
import { apiGet, apiPost, apiPut, ApiError } from '@/core/plugins/httpClient'
import type {
  RadioStats,
  ManualRecruitRequest,
  RecruitmentResponse,
  RadioMode,
} from '../models/radio'
import { useToast } from '@/core/composables/useToast'
import { handleStoreError } from '@/core/utils/errorHandler'

export const useRadioStore = defineStore('radio', () => {
  const toast = useToast()

  // State
  const radioStats = ref<RadioStats | null>(null)
  const isLoading = ref(false)
  const isRecruiting = ref(false)

  // Actions
  async function fetchRadioStats(vaultId: string) {
    isLoading.value = true
    try {
      radioStats.value = await apiGet<RadioStats>(`/api/v1/radio/vault/${vaultId}/stats`)
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch radio stats')
      toast.error(
        error instanceof ApiError
          ? typeof error.detail === 'string'
            ? error.detail
            : error.message
          : 'Failed to fetch radio stats'
      )
    } finally {
      isLoading.value = false
    }
  }

  async function manualRecruit(
    vaultId: string,
    request: ManualRecruitRequest = {}
  ): Promise<RecruitmentResponse | null> {
    isRecruiting.value = true
    try {
      const result = await apiPost<RecruitmentResponse>(
        `/api/v1/radio/vault/${vaultId}/recruit`,
        request
      )

      if (result.recycled) {
        toast.success(`📡 ${result.message} A familiar face answers the call from the wastes.`)
      } else {
        toast.success(result.message)
      }
      return result
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to recruit dweller')
      toast.error(
        error instanceof ApiError
          ? typeof error.detail === 'string'
            ? error.detail
            : error.message
          : 'Failed to recruit dweller'
      )
      return null
    } finally {
      isRecruiting.value = false
    }
  }

  /**
   * Format recruitment rate for display
   */
  function formatRecruitmentRate(stats: RadioStats | null): string {
    if (!stats || !stats.has_radio) {
      return 'No radio room'
    }

    if (stats.estimated_hours_per_recruit === 0) {
      return 'No recruitment possible'
    }

    const hours = stats.estimated_hours_per_recruit
    if (hours < 1) {
      const minutes = Math.round(hours * 60)
      return `~${minutes} min per recruit`
    } else if (hours < 24) {
      return `~${hours.toFixed(1)} hours per recruit`
    } else {
      const days = (hours / 24).toFixed(1)
      return `~${days} days per recruit`
    }
  }

  async function setRadioMode(vaultId: string, mode: RadioMode): Promise<boolean> {
    try {
      await apiPut(`/api/v1/radio/vault/${vaultId}/mode?mode=${mode}`)

      // Refresh stats after mode change
      await fetchRadioStats(vaultId)

      const modeLabel = mode === 'recruitment' ? 'Recruitment' : 'Happiness Boost'
      toast.success(`Radio mode set to ${modeLabel}`)
      return true
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to set radio mode')
      toast.error(
        error instanceof ApiError
          ? typeof error.detail === 'string'
            ? error.detail
            : error.message
          : 'Failed to set radio mode'
      )
      return false
    }
  }

  async function setRadioSpeedup(
    vaultId: string,
    roomId: string,
    speedup: number
  ): Promise<boolean> {
    try {
      await apiPut(`/api/v1/radio/vault/${vaultId}/room/${roomId}/speedup?speedup=${speedup}`)

      // Refresh stats after speedup change
      await fetchRadioStats(vaultId)

      toast.success(`Radio speedup set to ${speedup}x`)
      return true
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to set radio speedup')
      toast.error(
        error instanceof ApiError
          ? typeof error.detail === 'string'
            ? error.detail
            : error.message
          : 'Failed to set radio speedup'
      )
      return false
    }
  }

  function clearRadioStats() {
    radioStats.value = null
  }

  return {
    // State
    radioStats,
    isLoading,
    isRecruiting,

    // Actions
    fetchRadioStats,
    manualRecruit,
    setRadioMode,
    setRadioSpeedup,
    formatRecruitmentRate,
    clearRadioStats,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useRadioStore, import.meta.hot))
}
