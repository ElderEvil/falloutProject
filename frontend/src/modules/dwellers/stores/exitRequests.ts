import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'

type ExitRequest = components['schemas']['ExitRequestRead']
type ExitDecision = components['schemas']['ExitDecisionResponse']

export const useExitRequestStore = defineStore('exitRequests', () => {
  const toast = useToast()

  const requests = ref<ExitRequest[]>([])
  const isLoading = ref(false)
  let loadSequence = 0

  async function load(vaultId: string): Promise<void> {
    const sequence = ++loadSequence
    isLoading.value = true
    try {
      const response = await axios.get<ExitRequest[]>(
        `/api/v1/dwellers/vault/${vaultId}/exit-requests`
      )
      const loaded = response.data ?? []
      if (sequence === loadSequence) requests.value = loaded
    } catch (error) {
      toast.error(`Failed to load exit requests: ${getErrorMessage(error)}`)
    } finally {
      if (sequence === loadSequence) isLoading.value = false
    }
  }

  async function grant(vaultId: string, dwellerId: string): Promise<boolean> {
    try {
      const response = await axios.post<ExitDecision>(
        `/api/v1/dwellers/${dwellerId}/grant-exit`
      )
      const decision = response.data
      requests.value = requests.value.filter((request) => request.dweller_id !== dwellerId)
      toast.warning(`${decision.dweller_name} walked out and did not look back.`)
      return true
    } catch (error) {
      toast.error(`Failed to let the dweller go: ${getErrorMessage(error)}`)
      return false
    }
  }

  async function refuse(vaultId: string, dwellerId: string): Promise<boolean> {
    try {
      const response = await axios.post<ExitDecision>(
        `/api/v1/dwellers/${dwellerId}/refuse-exit`
      )
      const decision = response.data
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

  return { requests, isLoading, load, grant, refuse }
})
