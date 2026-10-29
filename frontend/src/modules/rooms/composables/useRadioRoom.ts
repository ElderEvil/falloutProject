import { notifyErrorOnce } from '@/core/utils/errorHandler'
import { getErrorMessage } from '@/core/types/utils'
import { computed, ref, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import type { Room } from '../models/room'
import { isRadioRoom } from '../models/roomParts'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useToast } from '@/core/composables/useToast'
import { getRadioStats, recruitDweller, setRadioMode } from '@/modules/radio/api/radio'

interface RadioStats {
  hasRadio: boolean
  recruitmentRate: number
  ratePerHour: number
  estimatedHoursPerRecruit: number
  manualCostCaps: number
  radioMode: string
  radioHappinessBonus: number
}

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
  const radioStats = ref<RadioStats | null>(null)

  const isRadio = computed(() => isRadioRoom(room.value))

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
    if (!vaultIdValue || typeof vaultIdValue !== 'string' || !isRadio.value) return

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      toast.error('Sign in is required to load radio stats')
      return
    }

    try {
      const data = await getRadioStats(vaultIdValue)
      if (data.manual_cost_caps != null) {
        manualRecruitCost.value = data.manual_cost_caps
      }
      radioStats.value = {
        hasRadio: data.has_radio ?? false,
        recruitmentRate: data.recruitment_rate ?? 0,
        ratePerHour: data.rate_per_hour ?? 0,
        estimatedHoursPerRecruit: data.estimated_hours_per_recruit ?? 0,
        manualCostCaps: data.manual_cost_caps ?? 0,
        radioMode: data.radio_mode ?? 'recruitment',
        radioHappinessBonus: data.radio_happiness_bonus ?? 0,
      }
    } catch (error) {
      notifyErrorOnce(error, 'Failed to load radio stats')
    }
  }

  watch(
    () => modelValue.value,
    (newValue) => {
      if (newValue && isRadio.value) {
        void loadRadioStats()
      }
    },
    { immediate: true }
  )

  const handleSwitchRadioMode = async (mode: 'recruitment' | 'happiness') => {
    const vaultIdValue = vaultId.value
    if (!vaultIdValue || typeof vaultIdValue !== 'string' || !isRadio.value) return

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      toast.error('Sign in is required to change radio mode')
      return
    }

    localRadioMode.value = mode

    try {
      await setRadioMode(vaultIdValue, mode)
    } catch (error) {
      localRadioMode.value =
        (vaultStore.activeVault?.radio_mode as 'recruitment' | 'happiness') || 'recruitment'
      notifyErrorOnce(error, 'Failed to switch radio mode')
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
    if (!vaultIdValue || typeof vaultIdValue !== 'string' || !isRadio.value) return

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
      const response = await recruitDweller(vaultIdValue)

      toast.success(response.message || 'Dweller recruited successfully!')

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
    } catch (error: unknown) {
      notifyErrorOnce(error, getErrorMessage(error, 'Failed to recruit dweller'))
    } finally {
      isRecruiting.value = false
    }
  }

  return {
    isRecruiting,
    isRadioRoom: isRadio,
    localRadioMode,
    manualRecruitCost,
    radioStats,
    handleSwitchRadioMode,
    handleRecruitDweller,
  }
}
