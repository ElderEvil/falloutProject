import { computed, ref, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useToast } from '@/core/composables/useToast'
import axios from '@/core/plugins/axios'

export function useRadioRoom(
  room: Ref<Room | null>,
  modelValue: Ref<boolean>,
  _assignedDwellers: Ref<DwellerShort[]>
) {
  const route = useRoute()
  const authStore = useAuthStore()
  const vaultStore = useVaultStore()
  const { filter: dwellerStore } = useDwellerStore()
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
      toast.error('Sign in is required to load radio stats')
      return
    }

    try {
      const response = await axios.get(`/api/v1/radio/vault/${vaultIdValue}/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (response.data?.manual_cost_caps != null) {
        manualRecruitCost.value = response.data.manual_cost_caps
      }
    } catch {
      toast.error('Failed to load radio stats')
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
      toast.error('Sign in is required to change radio mode')
      return
    }

    localRadioMode.value = mode

    try {
      await axios.put(
        `/api/v1/radio/vault/${vaultIdValue}/mode?mode=${mode}`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
    } catch {
      localRadioMode.value =
        (vaultStore.activeVault?.radio_mode as 'recruitment' | 'happiness') || 'recruitment'
      toast.error('Failed to switch radio mode')
      return
    }

    // Refresh vault (non-throwing) — separate from mutation error handling
    try {
      await vaultStore.refreshVault(vaultIdValue, token)
    } catch {
      toast.warning('Radio mode changed, but vault details could not refresh')
    }

    toast.success(`Radio mode set to ${mode}`)
  }

  const handleRecruitDweller = async () => {
    const vaultIdValue = vaultId.value
    if (!vaultIdValue || typeof vaultIdValue !== 'string' || !isRadioRoom.value) return

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      toast.error('Sign in is required to recruit dwellers')
      return
    }

    if (localRadioMode.value !== 'recruitment') {
      toast.error('Radio must be in Recruitment mode')
      return
    }

    isRecruiting.value = true
    try {
      const response = await axios.post(
        `/api/v1/radio/vault/${vaultIdValue}/recruit`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      )

      toast.success(response.data.message || 'Dweller recruited successfully!')

      // Refresh calls (non-throwing) — inside try so isRecruiting stays true until done
      try {
        await vaultStore.refreshVault(vaultIdValue, token)
      } catch {
        toast.warning('Dweller recruited, but vault details could not refresh')
      }
      try {
        await dwellerStore.fetchDwellersByVault(vaultIdValue, token)
      } catch {
        toast.warning('Dweller recruited, but the dweller list could not refresh')
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to recruit dweller'
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
