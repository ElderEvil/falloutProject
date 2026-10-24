import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import type { VaultBoyAnimationId } from '@/core/utils/vaultBoyAnimations'
import { ref, watch } from 'vue'
import { useToast } from '@/core/composables/useToast'
import { useVaultStore } from '../stores/vault'

interface WarningState {
  lastShown: number
}

const WARNING_ANIMATIONS: Record<string, VaultBoyAnimationId> = {
  low_food: 'empty-can',
  critical_food: 'empty-can',
  low_water: 'water-low',
  critical_water: 'water-low',
  critical_dehydration: 'water-low',
  low_power: 'power-low',
  critical_power: 'power-low',
}

const WARNING_COOLDOWN = 30000 // 30 seconds

export function useResourceWarnings() {
  const toast = useToast()
  const vaultStore = useVaultStore()
  const feedback = useVaultBoyFeedback()
  let warningVaultId: string | null = null

  const warningStates = ref<Record<string, WarningState>>({})

  watch(
    [() => vaultStore.activeVault, () => vaultStore.activeVaultId],
    ([vault]) => {
      if (warningVaultId !== vaultStore.activeVaultId) {
        warningStates.value = {}
        warningVaultId = vaultStore.activeVaultId
      }
      if (!vault?.resource_warnings) return

      const now = Date.now()

      vault.resource_warnings.forEach((warning) => {
        const lastState = warningStates.value[warning.type]

        if (!lastState || now - lastState.lastShown > WARNING_COOLDOWN) {
          const isCritical = warning.type.startsWith('critical_')

          if (isCritical) {
            toast.error(warning.message, 0) // Critical warnings don't auto-dismiss
          } else {
            toast.warning(warning.message, 5000) // Non-critical auto-dismiss after 5s
          }

          const animation = WARNING_ANIMATIONS[warning.type]
          if (animation && vaultStore.activeVaultId)
            feedback.show({
              animation,
              title: isCritical ? 'Critical resources' : 'Resources running low',
              message: warning.message,
              vaultId: vaultStore.activeVaultId,
              key: warning.type,
            })

          warningStates.value[warning.type] = {
            lastShown: now,
          }
        }
      })
    },
    { deep: true }
  )
}
