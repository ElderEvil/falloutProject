import { ref } from 'vue'
import { defineStore } from 'pinia'
import { getExitRequests, grantExit, refuseExit } from '../api/exitRequests'
import type { components } from '@/core/types/api.generated'
import { notifyErrorOnce, getErrorMessage } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'

type ExitRequest = components['schemas']['ExitRequestRead']

export const useExitRequestStore = defineStore('exitRequests', () => {
  const toast = useToast()

  const requests = ref<ExitRequest[]>([])
  const isLoading = ref(false)
  let loadSequence = 0

  async function load(vaultId: string): Promise<void> {
    const sequence = ++loadSequence
    isLoading.value = true
    try {
      const loaded = await getExitRequests(vaultId)
      if (sequence === loadSequence) requests.value = loaded
    } catch (error) {
      notifyErrorOnce(error, `Failed to load exit requests: ${getErrorMessage(error)}`)
    } finally {
      if (sequence === loadSequence) isLoading.value = false
    }
  }

  async function grant(dwellerId: string): Promise<boolean> {
    try {
      const decision = await grantExit(dwellerId)
      requests.value = requests.value.filter((request) => request.dweller_id !== dwellerId)
      toast.warning(`${decision.dweller_name} walked out and did not look back.`)
      return true
    } catch (error) {
      notifyErrorOnce(error, `Failed to let the dweller go: ${getErrorMessage(error)}`)
      return false
    }
  }

  async function refuse(dwellerId: string, happinessPenalty: number): Promise<boolean> {
    try {
      const decision = await refuseExit(dwellerId)
      requests.value = requests.value.filter((request) => request.dweller_id !== dwellerId)
      toast.warning(
        `${decision.dweller_name} stays. The vault loses ${happinessPenalty} happiness.`
      )
      return true
    } catch (error) {
      notifyErrorOnce(error, `Failed to refuse the request: ${getErrorMessage(error)}`)
      return false
    }
  }

  return { requests, isLoading, load, grant, refuse }
})
