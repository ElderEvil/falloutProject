import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type {
  RadioStats,
  ManualRecruitRequest,
  RecruitmentResponse,
  RadioMode,
} from '../models/radio'
import { useToast } from '@/core/composables/useToast'
import { useAsyncAction } from '@/core/composables/useAsyncAction'

export const useRadioStore = defineStore('radio', () => {
  const toast = useToast()

  // State
  const radioStats = ref<RadioStats | null>(null)
  const { run: runFetchRadioStats, isLoading } = useAsyncAction(
    async (vaultId: string) => {
      const response = await axios.get(`/api/v1/radio/vault/${vaultId}/stats`)
      radioStats.value = response.data
    },
    { context: 'Failed to fetch radio stats' }
  )
  const { run: runManualRecruit, isLoading: isRecruiting } = useAsyncAction(
    async (vaultId: string, request: ManualRecruitRequest = {}) => {
      const response = await axios.post(`/api/v1/radio/vault/${vaultId}/recruit`, request)
      const result: RecruitmentResponse = response.data

      if (result.recycled) {
        toast.success(`📡 ${result.message} A familiar face answers the call from the wastes.`)
      } else {
        toast.success(result.message)
      }
      return result
    },
    { context: 'Failed to recruit dweller' }
  )
  const { run: runSetRadioMode } = useAsyncAction(
    async (vaultId: string, mode: RadioMode) => {
      await axios.put(`/api/v1/radio/vault/${vaultId}/mode`, null, { params: { mode } })
      await fetchRadioStats(vaultId)
      const modeLabel = mode === 'recruitment' ? 'Recruitment' : 'Happiness Boost'
      toast.success(`Radio mode set to ${modeLabel}`)
      return true
    },
    { context: 'Failed to set radio mode' }
  )
  const { run: runSetRadioSpeedup } = useAsyncAction(
    async (vaultId: string, roomId: string, speedup: number) => {
      await axios.put(`/api/v1/radio/vault/${vaultId}/room/${roomId}/speedup`, null, {
        params: { speedup },
      })
      await fetchRadioStats(vaultId)
      toast.success(`Radio speedup set to ${speedup}x`)
      return true
    },
    { context: 'Failed to set radio speedup' }
  )

  // Actions
  async function fetchRadioStats(vaultId: string): Promise<void> {
    await runFetchRadioStats(vaultId)
  }

  async function manualRecruit(
    vaultId: string,
    request: ManualRecruitRequest = {}
  ): Promise<RecruitmentResponse | null> {
    return runManualRecruit(vaultId, request)
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
    return (await runSetRadioMode(vaultId, mode)) ?? false
  }

  async function setRadioSpeedup(
    vaultId: string,
    roomId: string,
    speedup: number
  ): Promise<boolean> {
    return (await runSetRadioSpeedup(vaultId, roomId, speedup)) ?? false
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
