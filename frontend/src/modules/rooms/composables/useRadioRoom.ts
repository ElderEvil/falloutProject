import { computed, ref, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useToast } from '@/core/composables/useToast'
import * as http from '@/core/plugins/httpClient'
import { handleStoreError } from '@/core/utils/errorHandler'

export function useRadioRoom(
  room: Ref<Room | null>,
  modelValue: Ref<boolean>,
  _assignedDwellers: Ref<DwellerShort[]>
) {
  const route = useRoute()
  const authStore = useAuthStore()
  const vaultStore = useVaultStore()
  const dwellerStore = useDwellerStore()
  const toast = useToast()

  const isRecruiting = ref(false)
  const manualRecruitCost = ref<number>(100)

  const isRadioRoom = computed(() => {
    return room.value?.name.toLowerCase().includes('radio') || false
  })

  const localRadioMode = ref(vaultStore.activeVault?.radio_mode || 'recruitment')

  watch(
    () => vaultStore.activeVault?.radio_mode,
    (newMode) => {
      if (newMode) {
        localRadioMode.value = newMode
      }
    }
  )

  const vaultId = computed(() => route.params.id)

  const loadRadioStats = async () => {
    const vaultIdValue = vaultId.value
    if (!vaultIdValue || typeof vaultIdValue !== 'string' || !isRadioRoom.value) return

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      console.error('Missing auth token for radio stats')
      return
    }

    try {
      const response = await http.apiGet<{ manual_cost_caps?: number }>(
        `/api/v1/radio/vault/${vaultIdValue}/stats`
      )
      if (response?.manual_cost_caps) {
        manualRecruitCost.value = response.manual_cost_caps
      }
    } catch (error) {
      handleStoreError(error, 'Failed to load radio stats')
    }
  }

  watch(
    () => modelValue.value,
    (newValue) => {
      if (newValue && isRadioRoom.value) {
        loadRadioStats()
      }
    },
    { immediate: true }
  )

  const handleSwitchRadioMode = async (mode: 'recruitment' | 'happiness') => {
    const vaultIdValue = vaultId.value
    if (!vaultIdValue || typeof vaultIdValue !== 'string' || !isRadioRoom.value) return

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      console.error('Missing auth token for radio mode change')
      return
    }

    localRadioMode.value = mode

    try {
      await http.apiPut(`/api/v1/radio/vault/${vaultIdValue}/mode?mode=${mode}`, {})

      await vaultStore.refreshVault(vaultIdValue, token)

      toast.success(`Radio mode set to ${mode}`)
    } catch (error) {
      localRadioMode.value =
        (vaultStore.activeVault?.radio_mode as 'recruitment' | 'happiness') || 'recruitment'
      handleStoreError(error, 'Failed to switch radio mode')
      toast.error('Failed to switch radio mode')
    }
  }

  const handleRecruitDweller = async () => {
    const vaultIdValue = vaultId.value
    if (!vaultIdValue || typeof vaultIdValue !== 'string' || !isRadioRoom.value) return

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      console.error('Missing auth token for dweller recruitment')
      return
    }

    if (localRadioMode.value !== 'recruitment') {
      toast.error('Radio must be in Recruitment mode')
      return
    }

    isRecruiting.value = true
    try {
      const response = await http.apiPost<{ message?: string }>(
        `/api/v1/radio/vault/${vaultIdValue}/recruit`,
        {}
      )

      toast.success(response?.message || 'Dweller recruited successfully!')

      await vaultStore.refreshVault(vaultIdValue, token)
      await dwellerStore.fetchDwellersByVault(vaultIdValue, token)
    } catch (error) {
      handleStoreError(error, 'Failed to recruit dweller')
      const message = error instanceof http.ApiError && error.detail
        ? (typeof error.detail === 'string' ? error.detail : 'Failed to recruit dweller')
        : 'Failed to recruit dweller'
      toast.error(message)
    } finally {
      isRecruiting.value = false
    }
  }

  return {
    isRecruiting,
    isRadioRoom,
    localRadioMode,
    manualRecruitCost,
    handleSwitchRadioMode,
    handleRecruitDweller,
  }
}
