import { ref } from 'vue'
import { defineStore } from 'pinia'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import {
  fetchExitRequests,
  grantExit,
  refuseExit,
  type ExitRequest,
} from '../services/exitRequestService'

export const useExitRequestStore = defineStore('exitRequests', () => {
  const toast = useToast()

  const requests = ref<ExitRequest[]>([])
  const isLoading = ref(false)
  let loadSequence = 0

  async function load(vaultId: string, token: string): Promise<void> {
    const sequence = ++loadSequence
    isLoading.value = true
    try {
      const loaded = await fetchExitRequests(vaultId, token)
      if (sequence === loadSequence) requests.value = loaded
    } catch (error) {
      toast.error(`Failed to load exit requests: ${getErrorMessage(error)}`)
    } finally {
      if (sequence === loadSequence) isLoading.value = false
    }
  }

  async function grant(vaultId: string, dwellerId: string, token: string): Promise<boolean> {
    try {
      const decision = await grantExit(vaultId, dwellerId, token)
      requests.value = requests.value.filter((request) => request.dweller_id !== dwellerId)
      toast.warning(`${decision.dweller_name} walked out and did not look back.`)
      return true
    } catch (error) {
      toast.error(`Failed to let the dweller go: ${getErrorMessage(error)}`)
      return false
    }
  }

  async function refuse(vaultId: string, dwellerId: string, token: string): Promise<boolean> {
    try {
      const decision = await refuseExit(vaultId, dwellerId, token)
      requests.value = requests.value.map((request) =>
        request.dweller_id === dwellerId ? { ...request, happiness: decision.happiness } : request
      )
      toast.info(`${decision.dweller_name} was refused. The request still stands.`)
      return true
    } catch (error) {
      toast.error(`Failed to refuse the request: ${getErrorMessage(error)}`)
      return false
    }
  }

  function forget(dwellerId: string): void {
    requests.value = requests.value.filter((request) => request.dweller_id !== dwellerId)
  }

  return { requests, isLoading, load, grant, refuse, forget }
})
