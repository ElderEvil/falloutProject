import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type { RadioStats, ManualRecruitRequest, RecruitmentResponse, RadioMode } from '../models/radio'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/types/utils'

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
      const response = await axios.get(`/api/v1/radio/vault/${vaultId}/stats`)
      radioStats.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch radio stats:', error)
      toast.error(getErrorMessage(error))
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
      const response = await axios.post(`/api/v1/radio/vault/${vaultId}/recruit`, request)
      const result: RecruitmentResponse = response.data

      toast.success(result.message)
      return result
    } catch (error: unknown) {
      console.error('Failed to recruit dweller:', error)
      toast.error(getErrorMessage(error))
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
      await axios.put(`/api/v1/radio/vault/${vaultId}/mode`, null, {
        params: { mode }
      })

      // Refresh stats after mode change
      await fetchRadioStats(vaultId)

      const modeLabel = mode === 'recruitment' ? 'Recruitment' : 'Happiness Boost'
      toast.success(`Radio mode set to ${modeLabel}`)
      return true
    } catch (error: unknown) {
      console.error('Failed to set radio mode:', error)
      toast.error(getErrorMessage(error))
      return false
    }
  }

  async function setRadioSpeedup(
    vaultId: string,
    roomId: string,
    speedup: number
  ): Promise<boolean> {
    try {
      await axios.put(`/api/v1/radio/vault/${vaultId}/room/${roomId}/speedup`, null, {
        params: { speedup }
      })

      // Refresh stats after speedup change
      await fetchRadioStats(vaultId)

      toast.success(`Radio speedup set to ${speedup}x`)
      return true
    } catch (error: unknown) {
      console.error('Failed to set radio speedup:', error)
      toast.error(getErrorMessage(error))
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
