import { ref, watch } from 'vue'
import { useToast } from '@/core/composables/useToast'
import { useVaultStore } from '../stores/vault'

interface WarningState {
  lastShown: number
}

const WARNING_COOLDOWN = 30000 // 30 seconds

export function useResourceWarnings() {
  const toast = useToast()
  const vaultStore = useVaultStore()

  const warningStates = ref<Record<string, WarningState>>({})

  watch(() => vaultStore.activeVault, (vault) => {
    if (!vault?.resource_warnings) return

    const now = Date.now()

    vault.resource_warnings.forEach((warning) => {
      const lastState = warningStates.value[warning.type]

      if (!lastState || (now - lastState.lastShown > WARNING_COOLDOWN)) {
        const isCritical = warning.type.startsWith('critical_')

        if (isCritical) {
          toast.error(warning.message, 0) // Critical warnings don't auto-dismiss
        } else {
          toast.warning(warning.message, 5000) // Non-critical auto-dismiss after 5s
        }

        warningStates.value[warning.type] = {
          lastShown: now
        }
      }
    })
  }, { deep: true })
}
